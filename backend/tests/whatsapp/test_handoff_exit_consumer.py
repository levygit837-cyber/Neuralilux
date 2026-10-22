"""Saída do Handoff vista pelo consumer: o Agent volta a responder depois de devolver ou do timeout."""
from datetime import timedelta

import pytest

from app.agent import executor
from app.agent.loop import TurnResult
from app.models import Conversation, Ticket
from app.services import handoff_service
from app.whatsapp.consumer import WhatsAppMessageConsumer
from consumer_helpers import process, upsert

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def real_handoff_gate(world, monkeypatch):
    """O Turn falso do `world` não olha o Handoff; aqui ele passa pelo mesmo gate do executor real."""
    fake_turn = executor.handle_incoming

    async def gated(db, conversation, contact, instance, text):
        if executor._in_handoff(db, conversation.id):
            return TurnResult(reply_text=None)
        return await fake_turn(db, conversation, contact, instance, text)

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
    ticket.created_at = handoff_service.utc_now() - timedelta(hours=5)  # timeout padrão da Company: 4h
    db.commit()

    await process(consumer, upsert(message_id="in-2", text="ninguém me atendeu"))

    db.expire_all()
    assert db.get(Ticket, ticket.id).status == "expired"
    assert db.get(Conversation, conversation.id).human_in_loop is False
    assert world["turns"] == ["ninguém me atendeu"]
    assert realtime[-1]["payload"]["change"] == "expired"


async def test_attendant_message_from_the_phone_postpones_the_timeout(db, world):
    consumer, conversation, ticket = await _conversation_in_handoff(db, world)
    ticket.created_at = handoff_service.utc_now() - timedelta(hours=5)
    db.commit()

    await process(consumer, upsert(message_id="mine-1", text="já te atendo", from_me=True))
    await process(consumer, upsert(message_id="in-2", text="obrigado"))

    db.expire_all()
    assert db.get(Ticket, ticket.id).status == "open"
    assert db.get(Conversation, conversation.id).human_in_loop is True
    assert world["turns"] == []
