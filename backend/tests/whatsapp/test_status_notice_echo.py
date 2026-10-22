"""Aviso de status do Order (#34) durante um Handoff: o eco `fromMe` dele nunca é atividade de Attendant (#35)."""
from datetime import timedelta

import pytest

from app.models import Conversation, Message, Ticket
from app.services import handoff_service
from app.services.order_status import change_status
from app.whatsapp.consumer import WhatsAppMessageConsumer
from app.whatsapp.evolution_client import evolution_api
from consumer_helpers import messages, process, upsert
from tests.order_helpers import make_order

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def realtime(monkeypatch):
    async def ignore(event):
        return None

    monkeypatch.setattr(handoff_service, "publish_event", ignore)


async def _handoff_with_order(db, world):
    """Conversation em Handoff há 3 h, sem nenhuma atividade de Attendant, com um Order recebido."""
    consumer = WhatsAppMessageConsumer()
    await process(consumer, upsert(message_id="in-1"))
    conversation = db.query(Conversation).one()
    order = make_order(db, world["instance"], "N-1", "closed", conversation=conversation)
    ticket = handoff_service.open_handoff(db, conversation, "Reclamação")
    ticket.created_at = handoff_service.clock.utc_now() - timedelta(hours=3)
    db.commit()
    world["turns"].clear()
    world["sent"].clear()
    return consumer, conversation, ticket, order


def _without_evolution_id(monkeypatch):
    async def send(*, instance_name, remote_jid, text):
        return {}

    monkeypatch.setattr(evolution_api, "send_text_message", send)


def _assert_handoff_untouched(db, conversation, ticket):
    db.expire_all()
    assert db.get(Conversation, conversation.id).human_in_loop is True
    stored = db.get(Ticket, ticket.id)
    assert stored.status == "open" and stored.attendant_activity_at is None  # o relógio do Handoff não andou


@pytest.mark.parametrize("evolution_returns_id", [True, False])
async def test_status_notice_echo_neither_reopens_the_agent_nor_resets_the_handoff_clock(
    db, world, monkeypatch, evolution_returns_id
):
    consumer, conversation, ticket, order = await _handoff_with_order(db, world)
    if not evolution_returns_id:
        _without_evolution_id(monkeypatch)

    await change_status(db, order, "in_production")
    notice = db.query(Message).filter(Message.sent_by == "system").one()
    echo_id = notice.message_id or "echo-1"
    await process(consumer, upsert(message_id=echo_id, text=notice.content, from_me=True))

    _assert_handoff_untouched(db, conversation, ticket)
    assert world["turns"] == []  # o Agent segue calado


@pytest.mark.parametrize("evolution_returns_id", [True, False])
async def test_status_notice_echo_is_deduplicated(db, world, monkeypatch, evolution_returns_id):
    consumer, conversation, ticket, order = await _handoff_with_order(db, world)
    if not evolution_returns_id:
        _without_evolution_id(monkeypatch)

    await change_status(db, order, "in_production")
    notice = db.query(Message).filter(Message.sent_by == "system").one()
    echo_id = notice.message_id or "echo-1"
    await process(consumer, upsert(message_id=echo_id, text=notice.content, from_me=True))
    await process(consumer, upsert(message_id=echo_id, text=notice.content, from_me=True))  # o webhook repete

    from_me = [m for m in messages(db) if m.is_from_me and m.content == notice.content]
    assert len(from_me) == 1 and from_me[0].message_id == echo_id and from_me[0].sent_by == "system"


async def test_attendant_message_still_counts_while_a_notice_without_id_waits_for_its_echo(db, world, monkeypatch):
    consumer, conversation, ticket, order = await _handoff_with_order(db, world)
    _without_evolution_id(monkeypatch)
    await change_status(db, order, "in_production")

    await process(consumer, upsert(message_id="mine-1", text="já te atendo, um minuto", from_me=True))

    db.expire_all()
    assert db.get(Ticket, ticket.id).attendant_activity_at is not None  # texto diferente do aviso: é um Attendant
