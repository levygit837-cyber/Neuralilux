"""#92: duas réplicas do worker (dois consumers) no mesmo Postgres nunca rodam dois Turns da mesma Conversation juntos,
respondem cada Message uma vez e não confundem o eco de uma resposta com um Attendant."""
import asyncio
import time
from collections import Counter
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.agent import executor
from app.agent.loop import TurnResult
from app.core import conversation_lock
from app.core.config import settings
from app.models import Agent, BusinessType, Company, Conversation, Instance, Message, Ticket
from app.services import handoff_service
from app.whatsapp import consumer as consumer_module, turn_state
from app.whatsapp.consumer import WhatsAppMessageConsumer
from app.whatsapp.evolution_client import evolution_api
from app.whatsapp.turn_runner import TurnRunner
from consumer_helpers import upsert
from tests.postgres.alembic_runner import run_alembic

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]


class Cluster:
    """Banco migrado compartilhado por todas as réplicas do teste, com o Turn e o envio falsos e registrados."""

    def __init__(self, engine):
        self.engine = engine
        self.turns: list[dict] = []  # um por Turn: texto, ids, quantas respostas já estavam gravadas ao começar
        self.sent: list[str] = []
        self.active = 0
        self.overlaps: list[int] = []

    def read(self, model, *criteria):
        with Session(self.engine) as db:
            query = db.query(model).filter(*criteria)
            rows = query.all()
            db.expunge_all()
            return rows

    def incoming(self) -> list[Message]:
        return self.read(Message, Message.direction == "incoming")

    def stored(self) -> list[tuple[str | None, str]]:
        rows = self.read(Message)
        return sorted((m.message_id, m.content) for m in rows)


@pytest.fixture
def cluster(make_database, monkeypatch):
    url = make_database()
    run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    with Session(engine) as db:
        business_type = BusinessType(name="Restaurante", slug="restaurant")
        db.add(business_type)
        db.flush()
        company = Company(name="Pizzaria", business_type_id=business_type.id)
        db.add(company)
        db.flush()
        agent = Agent(name="Atendente", system_prompt="", company_id=company.id, is_active=True)
        db.add(agent)
        db.flush()
        db.add(
            Instance(
                name="evo-t7", evolution_instance_id="evo-t7", company_id=company.id, agent_id=agent.id, agent_enabled=True
            )
        )
        db.commit()

    state = Cluster(engine)
    sent_ids = iter(f"out-{n}" for n in range(1, 100))

    async def fake_handle_incoming(
        db, conversation, contact, instance, text, received_at=None, message_ids=(), deferred_ids=(), agent=None, packs=()
    ):
        replies_seen = db.query(Message).filter(Message.conversation_id == conversation.id, Message.is_from_me.is_(True)).count()
        state.active += 1
        state.overlaps.append(state.active)
        state.turns.append({"text": text, "ids": tuple(message_ids), "replies_seen": replies_seen})
        try:
            await asyncio.sleep(0.3)  # tempo para um segundo Turn, se o lock deixasse, entrar junto
        finally:
            state.active -= 1
        return TurnResult(reply_text="Resposta")

    async def fake_send(*, instance_name, remote_jid, text):
        state.sent.append(text)
        return {"key": {"id": next(sent_ids)}}

    async def fake_refresh(conversation_id):
        return None

    async def fake_send_presence(instance_name, remote_jid, presence="composing", delay_ms=0):
        await asyncio.Event().wait()

    monkeypatch.setattr(executor, "handle_incoming", fake_handle_incoming)
    monkeypatch.setattr(executor, "refresh_summary", fake_refresh)
    monkeypatch.setattr(evolution_api, "send_text_message", fake_send)
    monkeypatch.setattr(evolution_api, "send_presence", fake_send_presence, raising=False)
    monkeypatch.setattr(consumer_module, "SessionLocal", sessionmaker(bind=engine, autoflush=False))
    monkeypatch.setattr(settings, "DEBOUNCE_SECONDS", 0.0)
    yield state
    conversation_lock.dispose_lock_engines()
    engine.dispose()


async def process(consumer: WhatsAppMessageConsumer, payload: dict) -> None:
    await consumer.process_webhook_event(payload)
    await consumer.drain()


# --- rajada dividida entre réplicas ---------------------------------------------------------------------


async def test_burst_split_between_replicas_never_overlaps_and_answers_each_message_once(cluster):
    a, b = WhatsAppMessageConsumer(), WhatsAppMessageConsumer()
    payloads = [upsert(text=f"m{n}", message_id=f"in-{n}") for n in range(8)]

    await asyncio.gather(*((a if n % 2 == 0 else b).process_webhook_event(p) for n, p in enumerate(payloads)))
    await asyncio.gather(a.drain(), b.drain())

    assert max(cluster.overlaps) == 1  # nunca dois Turns da Conversation ao mesmo tempo
    assert {(m.turn_state, m.turn_reason) for m in cluster.incoming()} == {(turn_state.ANSWERED, turn_state.REPLIED)}
    ids = Counter(i for turn in cluster.turns for i in turn["ids"])
    assert len(ids) == 8 and set(ids.values()) == {1}  # cada Message entrou em exatamente um Turn
    assert len(cluster.sent) == len(cluster.turns)  # um envio por Turn, nenhum a mais
    assert [turn["replies_seen"] for turn in cluster.turns] == list(range(len(cluster.turns)))  # cada Turn vê a resposta do anterior


async def test_message_reaching_the_other_replica_during_a_turn_waits_and_sees_the_reply(cluster):
    a, b = WhatsAppMessageConsumer(), WhatsAppMessageConsumer()

    await a.process_webhook_event(upsert(text="primeira", message_id="in-1"))
    for _ in range(200):  # o Turn da A está dentro do Agent
        if cluster.turns:
            break
        await asyncio.sleep(0.01)
    assert len(cluster.turns) == 1
    await b.process_webhook_event(upsert(text="segunda", message_id="in-2"))  # chega na B com o Turn da A em curso
    await asyncio.gather(a.drain(), b.drain())

    assert max(cluster.overlaps) == 1
    assert [(turn["text"], turn["replies_seen"]) for turn in cluster.turns] == [("primeira", 0), ("segunda", 1)]
    assert len(cluster.sent) == 2
    assert {(m.turn_state, m.turn_reason) for m in cluster.incoming()} == {(turn_state.ANSWERED, turn_state.REPLIED)}


async def test_turn_absorbs_what_the_other_replica_saved_and_the_burst_gets_one_reply(cluster, monkeypatch):
    """A réplica B gravou a primeira Message e ainda não rodou o Turn; o Turn da A toma as duas e responde uma vez."""
    a, b = WhatsAppMessageConsumer(), WhatsAppMessageConsumer()
    now = int(time.time())
    with monkeypatch.context() as patch:
        patch.setattr(TurnRunner, "spawn", lambda self, *args, **kwargs: None)  # B gravou e ainda não começou o Turn
        await b.process_webhook_event(upsert(text="primeira", message_id="in-1", ts=now - 2))

    await process(a, upsert(text="segunda", message_id="in-2", ts=now))

    assert [turn["text"] for turn in cluster.turns] == ["primeira\nsegunda"]
    assert len(cluster.sent) == 1
    assert {(m.message_id, m.turn_state, m.turn_reason) for m in cluster.incoming()} == {
        ("in-1", turn_state.ANSWERED, turn_state.REPLIED),
        ("in-2", turn_state.ANSWERED, turn_state.REPLIED),
    }


# --- eco entre réplicas -------------------------------------------------------------------------------------


async def test_echo_arriving_on_another_replica_while_the_reply_is_being_sent_is_adopted(cluster, monkeypatch):
    entered, gate = asyncio.Event(), asyncio.Event()

    async def slow_send_without_id(*, instance_name, remote_jid, text):
        entered.set()
        await gate.wait()
        return {"status": "ok"}

    monkeypatch.setattr(evolution_api, "send_text_message", slow_send_without_id)
    a, b = WhatsAppMessageConsumer(), WhatsAppMessageConsumer()

    replying = asyncio.create_task(process(a, upsert(text="Oi", message_id="in-1")))
    await asyncio.wait_for(entered.wait(), 10)
    echo = asyncio.create_task(process(b, upsert(text="Resposta", from_me=True, message_id="echo-1")))
    await asyncio.sleep(0.6)
    assert not echo.done()  # o eco espera a Message de saída ser gravada pela outra réplica
    gate.set()
    await asyncio.gather(replying, echo)

    assert cluster.stored() == [("echo-1", "Resposta"), ("in-1", "Oi")]  # a resposta ganhou o id do eco; nada duplicado


async def _handoff_after_a_reply_without_id(cluster, monkeypatch, a):
    async def send_without_id(*, instance_name, remote_jid, text):
        return {"status": "ok"}

    monkeypatch.setattr(evolution_api, "send_text_message", send_without_id)
    await process(a, upsert(text="Oi", message_id="in-1"))  # o Agent responde "Resposta", sem id da Evolution
    with Session(cluster.engine) as db:
        conversation = db.query(Conversation).one()
        ticket = handoff_service.open_handoff(db, conversation, "Reclamação")
        ticket.created_at = handoff_service.clock.utc_now() - timedelta(hours=5)
        db.commit()
        return ticket.id, conversation.id


async def test_echo_on_the_other_replica_is_not_attendant_activity(cluster, monkeypatch):
    a, b = WhatsAppMessageConsumer(), WhatsAppMessageConsumer()
    ticket_id, conversation_id = await _handoff_after_a_reply_without_id(cluster, monkeypatch, a)

    await process(b, upsert(text="Resposta", from_me=True, message_id="echo-1"))  # a A respondeu; o eco cai na B

    [ticket] = cluster.read(Ticket, Ticket.id == ticket_id)
    [conversation] = cluster.read(Conversation, Conversation.id == conversation_id)
    assert ticket.attendant_activity_at is None
    assert conversation.human_in_loop is True
    assert cluster.stored() == [("echo-1", "Resposta"), ("in-1", "Oi")]


async def test_attendant_typing_on_the_phone_still_counts_on_any_replica(cluster, monkeypatch):
    """Contraprova: o que não é eco de uma resposta nossa continua reiniciando o timeout do Handoff."""
    a, b = WhatsAppMessageConsumer(), WhatsAppMessageConsumer()
    ticket_id, _ = await _handoff_after_a_reply_without_id(cluster, monkeypatch, a)

    await process(b, upsert(text="Já resolvo isso", from_me=True, message_id="att-1"))

    [ticket] = cluster.read(Ticket, Ticket.id == ticket_id)
    assert ticket.attendant_activity_at is not None
