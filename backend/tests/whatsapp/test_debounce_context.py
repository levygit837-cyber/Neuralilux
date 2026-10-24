"""Rajada picada pelo caminho real (consumer, batcher e executor): o modelo vê cada Message uma vez, na ordem.

Só o Gateway (roteirizado) e o envio da Evolution são falsos. Relógio falso para a janela de agrupamento.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from agent_fakes import FakeMessagesClient, reply, text, tool_use, without_turn_context
from consumer_helpers import JID, messages, upsert

from app.agent import executor
from app.core.config import settings
from app.models import Agent, Contact, Conversation, CustomerOrder, Ticket
from app.realtime.event_bus import realtime_event_bus
from app.whatsapp import consumer as consumer_module
from app.whatsapp.consumer import WhatsAppMessageConsumer
from app.whatsapp.turn_runner import MEDIA_REPLY
from app.whatsapp.evolution_client import evolution_api
from app.whatsapp.turn_batcher import TurnBatcher
from tests.conftest import TestingSessionLocal
from tests.clock_helpers import FakeClock, settle

pytestmark = pytest.mark.asyncio

REAL_HANDLE_INCOMING = executor.handle_incoming  # antes de o `world` trocá-lo pelo Turn falso
IMAGE = {"imageMessage": {"mimetype": "image/jpeg"}}


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def model(world, monkeypatch):
    """Executor real, modelo roteirizado: `client.requests` guarda o que o modelo recebeu."""
    client = FakeMessagesClient([reply(text("ok")) for _ in range(5)])
    monkeypatch.setattr(executor, "handle_incoming", REAL_HANDLE_INCOMING)
    monkeypatch.setattr(executor, "resolve_gateway", lambda agent_type: (client, "fake-model", "low"))
    return client


@pytest.fixture
def consumer(clock, model):
    instance = WhatsAppMessageConsumer()
    instance.runner.batcher = TurnBatcher(monotonic=clock.monotonic, sleep=clock.sleep)
    instance._started_at = datetime.now(timezone.utc) - timedelta(days=2)  # nenhuma Message é backlog
    return instance


@pytest.fixture
def window(monkeypatch):
    monkeypatch.setattr(settings, "DEBOUNCE_SECONDS", 3.0)


def deliver(consumer, **kwargs):
    return asyncio.create_task(consumer.process_webhook_event(upsert(**kwargs)))


def user_inputs(model) -> list[list[dict]]:
    return [without_turn_context(request.messages) for request in model.requests]


async def test_text_media_text_in_one_window_is_one_turn_with_exactly_the_two_texts(
    db, world, model, consumer, clock, window
):
    tasks = [deliver(consumer, text="oi", message_id="in-1")]
    await settle()
    tasks.append(deliver(consumer, message_id="in-2", message=IMAGE))
    await settle()
    tasks.append(deliver(consumer, text="quero", message_id="in-3"))
    await settle()
    await clock.advance(3)
    await asyncio.gather(*tasks)
    await consumer.drain()

    assert user_inputs(model) == [[{"role": "user", "content": "oi\nquero"}]]
    assert [sent["text"] for sent in world["sent"]] == [MEDIA_REPLY, "ok"]  # a mídia é respondida uma vez


async def test_burst_across_a_session_boundary_is_not_duplicated_and_abandons_the_order_once(
    db, world, model, consumer, clock, window, monkeypatch
):
    settings.DEBOUNCE_SECONDS = 0.0
    long_ago = datetime.now(timezone.utc) - timedelta(hours=8)
    first = deliver(consumer, text="oi antigo", message_id="old-1", ts=int(long_ago.timestamp()))
    await settle()
    await first
    await consumer.drain()
    conversation = db.query(Conversation).one()
    conversation.last_message_at = long_ago
    db.add(
        CustomerOrder(
            order_number="T-1",
            conversation_id=conversation.id,
            instance_id=conversation.instance_id,
            contact_id=db.query(Contact).one().id,
            remote_jid=JID,
            status="open",
        )
    )
    db.commit()
    model.requests.clear()

    rolled = []
    real_roll = consumer_module.roll_session

    def counting_roll(*args, **kwargs):
        opened = real_roll(*args, **kwargs)
        rolled.append(opened)
        return opened

    monkeypatch.setattr(consumer_module, "roll_session", counting_roll)
    monkeypatch.setattr(settings, "DEBOUNCE_SECONDS", 3.0)
    back = int((long_ago + timedelta(hours=7)).timestamp())
    tasks = [deliver(consumer, text="msg1", message_id="new-1", ts=back)]
    await settle()
    tasks.append(deliver(consumer, text="msg2", message_id="new-2", ts=back + 1))
    await settle()
    await clock.advance(3)
    await asyncio.gather(*tasks)
    await consumer.drain()

    assert user_inputs(model) == [[{"role": "user", "content": "msg1\nmsg2"}]]
    assert rolled.count(True) == 1
    assert db.query(CustomerOrder).one().status == "abandoned"


async def test_follower_stored_when_the_window_closes_joins_the_group_and_is_answered_once(
    db, world, model, consumer, clock, window, monkeypatch
):
    follower_may_publish = asyncio.Event()
    real_publish = consumer_module.publish_message

    async def publish(conversation, contact, message_id, *args):
        if message_id == "in-2":
            await follower_may_publish.wait()  # já commitada; ainda não chegou ao batcher
        return await real_publish(conversation, contact, message_id, *args)

    monkeypatch.setattr(consumer_module, "publish_message", publish)
    leader = deliver(consumer, text="oi", message_id="in-1")
    await settle()
    follower = deliver(consumer, text="quero", message_id="in-2")
    await settle()
    assert [m.content for m in messages(db)] == ["oi", "quero"] and not follower.done()

    await clock.advance(3)  # a janela da líder fecha com a seguidora a caminho
    assert user_inputs(model) == []

    follower_may_publish.set()
    await settle()
    await clock.advance(3)
    await asyncio.gather(leader, follower)
    await consumer.drain()

    assert user_inputs(model) == [[{"role": "user", "content": "oi\nquero"}]]
    assert [sent["text"] for sent in world["sent"]] == ["ok"]


# --- rajada + Handoff -------------------------------------------------------------------------------


@pytest.fixture
def handoff_events(monkeypatch):
    """A Tool de transferência e o service publicam no Redis; aqui só registram."""
    published = []

    async def capture(event):
        published.append(event)

    monkeypatch.setattr(realtime_event_bus, "publish", capture)
    return published


class GatedClient(FakeMessagesClient):
    """Segura a primeira chamada do modelo até o teste soltar: dá tempo de chegar Message no meio do Turn."""

    def __init__(self, script):
        super().__init__(script)
        self.gate = asyncio.Event()

    async def create(self, request):
        if not self.requests:
            await self.gate.wait()
        return await super().create(request)


async def test_transfer_requested_in_a_burst_transfers_once_and_later_messages_do_not_run_the_agent(
    db, world, consumer, clock, window, handoff_events, monkeypatch
):
    client = GatedClient([reply(tool_use("transferir_atendente", {"motivo": "pediu um humano"}, "t1"))])
    monkeypatch.setattr(executor, "resolve_gateway", lambda agent_type: (client, "fake-model", "low"))

    tasks = [deliver(consumer, text="quero falar com um atendente", message_id="in-1")]
    await settle()
    tasks.append(deliver(consumer, text="por favor", message_id="in-2"))
    await settle()
    await clock.advance(3)  # o Turn começa e fica preso no modelo
    late = deliver(consumer, text="alguém aí?", message_id="in-3")  # chega durante o Turn
    await settle()
    client.gate.set()
    await settle()
    await clock.advance(3)  # pausa da Message tardia: o Turn seguinte já nasce em Handoff
    await asyncio.gather(*tasks, late)
    await consumer.drain()

    assert len(client.requests) == 1  # um só Turn chegou ao modelo
    assert without_turn_context(client.requests[0].messages) == [
        {"role": "user", "content": "quero falar com um atendente\npor favor"}
    ]
    assert db.query(Ticket).count() == 1
    handoff_requests = [e for e in handoff_events if e["type"] == "human_handoff_requested"]
    assert len(handoff_requests) == 1
    assert handoff_requests[0]["payload"]["conversation_id"] == db.query(Conversation).one().id
    assert len(world["sent"]) == 1  # só a frase da transferência
    assert db.query(Conversation).one().human_in_loop is True


async def test_attendant_taking_over_during_the_window_prevents_the_turn(
    db, world, model, consumer, clock, window
):
    leader = deliver(consumer, text="oi", message_id="in-1")
    await settle()
    follower = deliver(consumer, text="quero", message_id="in-2")
    await settle()

    other = TestingSessionLocal()  # o painel do Attendant, em outra Session
    try:
        other.query(Conversation).update({"human_in_loop": True})
        other.commit()
    finally:
        other.close()
    await clock.advance(3)
    await asyncio.gather(leader, follower)
    await consumer.drain()

    assert model.requests == []
    assert world["sent"] == []
    assert [m.content for m in messages(db)] == ["oi", "quero"]  # as Messages continuam gravadas


# --- DEBOUNCE_SECONDS=0 -----------------------------------------------------------------------------


async def test_without_grouping_each_message_gets_its_own_turn_and_the_queued_ones_stay_out_of_its_history(
    db, world, consumer, clock, monkeypatch
):
    client = GatedClient([reply(text("r1")), reply(text("r2")), reply(text("r3"))])
    monkeypatch.setattr(executor, "handle_incoming", REAL_HANDLE_INCOMING)
    monkeypatch.setattr(executor, "resolve_gateway", lambda agent_type: (client, "fake-model", "low"))
    assert settings.DEBOUNCE_SECONDS == 0.0  # padrão dos testes do consumer: agrupamento desligado
    base = int(datetime.now(timezone.utc).timestamp()) - 60  # no passado: as respostas (agora) vêm depois, em ordem fixa

    first = deliver(consumer, text="oi", message_id="in-1", ts=base)
    await settle()  # o Turn de "oi" começa e fica preso no modelo
    second = deliver(consumer, text="quero", message_id="in-2", ts=base + 1)
    third = deliver(consumer, text="uma calabresa", message_id="in-3", ts=base + 2)
    await settle()
    assert second.done() and third.done() and client.requests == []

    client.gate.set()
    await asyncio.gather(first, second, third)
    await consumer.drain()

    assert user_inputs(model=client) == [
        [{"role": "user", "content": "oi"}],
        # "uma calabresa" já está gravada, mas é do Turn seguinte: não entra no histórico deste.
        [{"role": "user", "content": "oi"}, {"role": "assistant", "content": "r1"}, {"role": "user", "content": "quero"}],
        [
            {"role": "user", "content": "oi\nquero"},
            {"role": "assistant", "content": "r1\nr2"},
            {"role": "user", "content": "uma calabresa"},
        ],
    ]
    assert [sent["text"] for sent in world["sent"]] == ["r1", "r2", "r3"]


async def test_turn_uses_temperature_and_max_tokens_of_the_agent_bound_to_the_instance(
    db, world, model, consumer
):
    # Um Agent mais antigo na mesma Company: o Turn não pode escolhê-lo no lugar do vinculado.
    older = Agent(
        name="Mais antigo", company_id=world["company"].id, is_active=True, temperature=0.9, max_tokens=111,
        created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    db.add(older)
    bound = world["agent"]
    bound.temperature, bound.max_tokens = 0.2, 700
    db.commit()

    await consumer.process_webhook_event(upsert(text="oi", message_id="in-1"))
    await consumer.drain()

    request = model.requests[0]
    assert (request.temperature, request.max_tokens) == (0.2, 700)
