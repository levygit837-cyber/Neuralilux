"""Saída do Handoff vista pelo consumer: o Agent volta a responder depois de devolver ou do timeout."""
from datetime import timedelta

import pytest

from app.agent import executor
from app.agent.loop import TurnResult
from app.models import Conversation, Ticket
from app.whatsapp.evolution_client import evolution_api
from app.services import handoff_service
from app.whatsapp.consumer import WhatsAppMessageConsumer
from consumer_helpers import process, upsert

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def real_handoff_gate(world, monkeypatch):
    """O Turn falso do `world` não olha o Handoff; aqui ele passa pelo mesmo gate do executor real."""
    fake_turn = executor.handle_incoming

    async def gated(db, conversation, contact, instance, text, received_at=None, message_ids=(), deferred_ids=(), agent=None):
        if executor._in_handoff(db, conversation.id):
            return TurnResult(reply_text=None)
        return await fake_turn(db, conversation, contact, instance, text, received_at)

    monkeypatch.setattr(executor, "handle_incoming", gated)


@pytest.fixture(autouse=True)
def realtime(monkeypatch):
    published: list[dict] = []

    async def capture(event):
        published.append(event)

    monkeypatch.setattr(handoff_service, "publish_event", capture)
    return published


async def _conversation_in_handoff(db, world):
    """Primeira Message cria a Conversation (Agent responde); depois ela entra em Handoff."""
    consumer = WhatsAppMessageConsumer()
    await process(consumer, upsert(message_id="in-1"))
    world["turns"].clear()
    world["sent"].clear()
    conversation = db.query(Conversation).one()
    ticket = handoff_service.open_handoff(db, conversation, "Reclamação")
    return consumer, conversation, ticket


async def test_agent_stays_silent_during_handoff_and_answers_after_release(db, world):
    consumer, conversation, _ = await _conversation_in_handoff(db, world)

    await process(consumer, upsert(message_id="in-2", text="alguém aí?"))
    assert world["turns"] == [] and world["sent"] == []

    handoff_service.release(db, conversation)
    await process(consumer, upsert(message_id="in-3", text="e agora?"))
    assert world["turns"] == ["e agora?"]
    assert [m["text"] for m in world["sent"]] == ["Resposta"]


async def test_overdue_handoff_expires_on_the_next_message_and_agent_answers(db, world, realtime):
    consumer, conversation, ticket = await _conversation_in_handoff(db, world)
    ticket.created_at = handoff_service.clock.utc_now() - timedelta(hours=5)  # timeout padrão da Company: 4h
    db.commit()

    await process(consumer, upsert(message_id="in-2", text="ninguém me atendeu"))

    db.expire_all()
    assert db.get(Ticket, ticket.id).status == "expired"
    assert db.get(Conversation, conversation.id).human_in_loop is False
    assert world["turns"] == ["ninguém me atendeu"]
    assert realtime[-1]["payload"]["change"] == "expired"


async def test_attendant_message_from_the_phone_postpones_the_timeout(db, world):
    consumer, conversation, ticket = await _conversation_in_handoff(db, world)
    ticket.created_at = handoff_service.clock.utc_now() - timedelta(hours=5)
    db.commit()

    await process(consumer, upsert(message_id="mine-1", text="já te atendo", from_me=True))
    await process(consumer, upsert(message_id="in-2", text="obrigado"))

    db.expire_all()
    assert db.get(Ticket, ticket.id).status == "open"
    assert db.get(Conversation, conversation.id).human_in_loop is True
    assert world["turns"] == []


async def test_agent_reply_echo_with_a_known_id_does_not_restart_the_attendant_clock(db, world):
    """O Agent respondeu (com id) e depois a Conversation entrou em Handoff; o eco `fromMe` da resposta é só dedup."""
    consumer = WhatsAppMessageConsumer()
    await process(consumer, upsert(message_id="in-1"))
    conversation = db.query(Conversation).one()
    assert [m["text"] for m in world["sent"]] == ["Resposta"]
    ticket = handoff_service.open_handoff(db, conversation, "Reclamação")

    await process(consumer, upsert(text="Resposta", from_me=True, message_id="out-1"))  # id que o Agent gravou

    db.expire_all()
    assert db.get(Ticket, ticket.id).attendant_activity_at is None


async def test_echo_of_an_agent_reply_sent_without_id_does_not_restart_the_attendant_clock(db, world, monkeypatch):
    async def send_without_id(**_kwargs):
        return {"status": "ok"}

    monkeypatch.setattr(evolution_api, "send_text_message", send_without_id)
    consumer = WhatsAppMessageConsumer()
    await process(consumer, upsert(message_id="in-1"))  # o Agent responde "Resposta", sem id da Evolution
    conversation = db.query(Conversation).one()
    ticket = handoff_service.open_handoff(db, conversation, "Reclamação")
    ticket.created_at = handoff_service.clock.utc_now() - timedelta(hours=5)
    db.commit()

    await process(consumer, upsert(text="Resposta", from_me=True, message_id="echo-1"))

    db.expire_all()
    assert db.get(Ticket, ticket.id).attendant_activity_at is None
    assert db.get(Conversation, conversation.id).human_in_loop is True


async def test_attendant_message_with_the_same_text_as_a_past_reply_still_counts(db, world, monkeypatch):
    """O eco sem id vale uma vez: um segundo `fromMe` igual é um Attendant de verdade."""
    async def send_without_id(**_kwargs):
        return {"status": "ok"}

    monkeypatch.setattr(evolution_api, "send_text_message", send_without_id)
    consumer = WhatsAppMessageConsumer()
    await process(consumer, upsert(message_id="in-1"))
    conversation = db.query(Conversation).one()
    ticket = handoff_service.open_handoff(db, conversation, "Reclamação")
    await process(consumer, upsert(text="Resposta", from_me=True, message_id="echo-1"))  # eco consumido
    db.expire_all()
    assert db.get(Ticket, ticket.id).attendant_activity_at is None

    await process(consumer, upsert(text="Resposta", from_me=True, message_id="phone-1"))  # agora é o celular

    db.expire_all()
    assert db.get(Ticket, ticket.id).attendant_activity_at is not None
