"""Envio pelo painel (#94): o mesmo `send_and_persist` do worker. Falha ao gravar depois do envio não vira 500 nem duplica
a Message: o eco do webhook (mesmo id) a cria ou o dedup o descarta."""
import asyncio

import pytest
from sqlalchemy.exc import OperationalError

from app.models import Conversation, Message
from app.whatsapp import sender
from consumer_helpers import process, upsert
from tests.access_helpers import make_user
from app.whatsapp.consumer import WhatsAppMessageConsumer

pytestmark = pytest.mark.asyncio

JID = "5511999990001@s.whatsapp.net"


@pytest.fixture
def panel(client, db, world):
    headers = make_user(client, db, "painel@example.com", superuser=True)
    instance = world["instance"]
    instance.status = "connected"
    conversation = Conversation(instance_id=instance.id, contact_id=_contact(db, instance).id, remote_jid=JID, is_active=True)
    db.add(conversation)
    db.commit()
    return headers, conversation


def _contact(db, instance):
    from app.models import Contact

    contact = Contact(instance_id=instance.id, phone_number="5511999990001", remote_jid=JID, name="Cliente")
    db.add(contact)
    db.commit()
    return contact


def _stored(db) -> list[Message]:
    db.expire_all()
    return db.query(Message).filter(Message.is_from_me.is_(True)).all()


async def _send(client, headers, conversation):
    return await asyncio.to_thread(
        client.post,
        f"/api/v1/conversations/{conversation.id}/messages",
        json={"content": "Oi pelo painel", "message_type": "text"},
        headers=headers,
    )


async def test_panel_send_persists_through_the_worker_path(client, db, world, panel):
    headers, conversation = panel

    response = await _send(client, headers, conversation)

    assert response.status_code == 200 and response.json()["message_id"] == "out-1"
    [stored] = _stored(db)
    assert (stored.message_id, stored.content, stored.sent_by) == ("out-1", "Oi pelo painel", None)  # Attendant: sem `sent_by`
    assert len(world["sent"]) == 1


async def test_database_failure_after_the_send_is_not_a_500_and_the_echo_creates_the_message_once(
    client, db, world, panel, monkeypatch
):
    headers, conversation = panel

    def broken(*args, **kwargs):
        raise OperationalError("INSERT", {}, Exception("banco fora"))

    monkeypatch.setattr(sender, "_persist_reply", broken)

    response = await _send(client, headers, conversation)

    assert response.status_code == 200 and response.json()["message_id"] == "out-1"
    assert len(world["sent"]) == 1  # saiu uma vez, sem retry
    assert _stored(db) == []

    consumer = WhatsAppMessageConsumer()
    echo = upsert(text="Oi pelo painel", remote_jid=JID, message_id="out-1", from_me=True)
    await process(consumer, echo)
    await process(consumer, echo)  # entrega repetida do mesmo eco

    [stored] = _stored(db)
    assert (stored.message_id, stored.content) == ("out-1", "Oi pelo painel")


async def test_echo_after_a_successful_panel_send_does_not_duplicate(client, db, world, panel):
    headers, conversation = panel
    await _send(client, headers, conversation)

    await process(WhatsAppMessageConsumer(), upsert(text="Oi pelo painel", remote_jid=JID, message_id="out-1", from_me=True))

    assert len(_stored(db)) == 1


async def test_echo_adopts_the_row_saved_without_an_evolution_id(client, db, world, panel, monkeypatch):
    headers, conversation = panel

    async def no_id(*, instance_name, remote_jid, text):
        return {}

    monkeypatch.setattr(sender.evolution_api, "send_text_message", no_id)
    await _send(client, headers, conversation)
    [saved] = _stored(db)
    assert saved.message_id is None

    await process(WhatsAppMessageConsumer(), upsert(text="Oi pelo painel", remote_jid=JID, message_id="out-9", from_me=True))

    [adopted] = _stored(db)
    assert adopted.id == saved.id and adopted.message_id == "out-9"
