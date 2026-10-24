"""A Evolution reenvia webhooks fora de ordem e com atraso: status de Message e conexão só avançam."""
from datetime import datetime, timezone

import pytest
import structlog

from app.models import Contact, Conversation, Instance, Message, User
from app.whatsapp import status_events
from app.whatsapp.status_events import update_connection_status, update_message_status


@pytest.fixture
def owned_instance(db):
    db.add(User(id="user-replay", email="replay@example.com", hashed_password="x", full_name="Replay", is_active=True))
    db.flush()
    instance = Instance(id="instance-replay", name="Replay", evolution_instance_id="evo-realtime-1",
                        status="disconnected", is_active=True, owner_id="user-replay")
    db.add(instance)
    db.commit()
    return instance


@pytest.fixture
def published(monkeypatch):
    events = []

    async def capture(event):
        events.append(event)

    monkeypatch.setattr("app.realtime.event_bus.realtime_event_bus.publish", capture)
    monkeypatch.setattr(status_events, "_last_connection_event", {})
    return events


def _message(db, instance, status="sent"):
    contact = Contact(id="c-replay", instance_id=instance.id, phone_number="5511999999999",
                      remote_jid="5511999999999@s.whatsapp.net", name="Contato")
    db.add(contact)
    db.flush()
    conversation = Conversation(id="cv-replay", instance_id=instance.id, contact_id=contact.id,
                                remote_jid=contact.remote_jid, is_active=True)
    db.add(conversation)
    db.flush()
    message = Message(id="db-replay", instance_id=instance.id, conversation_id=conversation.id,
                      remote_jid=contact.remote_jid, message_id="msg-replay", message_type="text", content="x",
                      direction="outgoing", status=status, is_from_me=True, timestamp=datetime.now(timezone.utc))
    db.add(message)
    db.commit()
    return message


def _update(status, key_id="msg-replay"):
    return {"instance": "evo-realtime-1", "data": {"keyId": key_id, "status": status}}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "start, received, expected",
    [
        ("read", "DELIVERY_ACK", "read"),  # reenvio atrasado do ack de entrega
        ("read", "SERVER_ACK", "read"),
        ("delivered", "SERVER_ACK", "delivered"),
        ("read", "READ", "read"),
        ("sent", "DELIVERY_ACK", "delivered"),
        ("sent", "PLAYED", "read"),
        ("pending", "ERROR", "failed"),
        ("failed", "SERVER_ACK", "sent"),  # um ack real tira de `failed`
        ("sent", "ERROR", "sent"),  # erro tardio não desfaz o que já foi enviado
        ("delivered", "DELETED", "delivered"),  # não é progresso de entrega
    ],
)
async def test_message_status_only_moves_forward(db, owned_instance, published, start, received, expected):
    message = _message(db, owned_instance, status=start)

    await update_message_status(db, _update(received))
    db.refresh(message)

    assert message.status == expected
    assert [e["payload"]["status"] for e in published] == ([expected] if expected != start else [])


@pytest.mark.asyncio
async def test_stale_status_is_ignored_with_a_debug_log_and_no_ui_event(db, owned_instance, published):
    _message(db, owned_instance, status="read")

    with structlog.testing.capture_logs() as logs:
        await update_message_status(db, _update("DELIVERY_ACK"))

    assert [log["log_level"] for log in logs if log["event"] == "Stale message status ignored"] == ["debug"]
    assert published == []


@pytest.mark.asyncio
async def test_status_for_a_message_not_stored_yet_is_logged(db, owned_instance, published):
    with structlog.testing.capture_logs() as logs:
        await update_message_status(db, _update("READ", key_id="ainda-nao-existe"))

    discarded = [log for log in logs if log["event"].startswith("Message status update for unknown message")]
    assert [(log["message_id"], log["log_level"]) for log in discarded] == [("ainda-nao-existe", "warning")]
    assert published == []


def _connection(state, date_time):
    return {"instance": "evo-realtime-1", "date_time": date_time, "data": {"state": state}}


@pytest.mark.asyncio
async def test_replayed_older_connection_update_does_not_overwrite_a_newer_one(db, owned_instance, published):
    await update_connection_status(db, _connection("open", "2026-01-01T12:10:00.000-03:00"))
    await update_connection_status(db, _connection("close", "2026-01-01T12:00:00.000-03:00"))  # reenvio velho
    db.refresh(owned_instance)

    assert owned_instance.status == "connected"
    assert [e["payload"]["status"] for e in published] == ["connected"]


@pytest.mark.asyncio
async def test_newer_and_identical_event_times_are_applied(db, owned_instance, published):
    await update_connection_status(db, _connection("open", "2026-01-01T12:00:00.000-03:00"))
    await update_connection_status(db, _connection("close", "2026-01-01T12:00:00.000-03:00"))
    await update_connection_status(db, _connection("open", "2026-01-01T12:05:00.000-03:00"))
    db.refresh(owned_instance)

    assert owned_instance.status == "connected"
    assert [e["payload"]["status"] for e in published] == ["connected", "disconnected", "connected"]


@pytest.mark.asyncio
async def test_connection_update_without_date_time_is_applied_as_before(db, owned_instance, published):
    await update_connection_status(db, _connection("open", "2026-01-01T12:00:00.000-03:00"))
    await update_connection_status(db, {"instance": "evo-realtime-1", "data": {"state": "close"}})
    db.refresh(owned_instance)

    assert owned_instance.status == "disconnected"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "remote_jid, level",
    [("status@broadcast", "debug"), ("123456@broadcast", "debug"), ("5511999999999@s.whatsapp.net", "warning")],
)
async def test_unknown_message_log_level_depends_on_the_chat(db, owned_instance, published, remote_jid, level):
    update = {"instance": "evo-realtime-1", "data": {"keyId": "x", "remoteJid": remote_jid, "status": "READ"}}

    with structlog.testing.capture_logs() as logs:
        await update_message_status(db, update)

    discarded = [log for log in logs if log["event"].startswith("Message status update for unknown message")]
    assert [log["log_level"] for log in discarded] == [level]


@pytest.mark.asyncio
async def test_connection_update_reports_whether_it_was_applied(db, owned_instance, published):
    assert await update_connection_status(db, _connection("open", "2026-01-01T12:10:00.000-03:00")) is True
    assert await update_connection_status(db, _connection("close", "2026-01-01T12:00:00.000-03:00")) is False
    assert await update_connection_status(db, {"instance": "desconhecida", "data": {"state": "open"}}) is False
