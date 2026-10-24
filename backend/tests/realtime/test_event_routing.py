"""Roteamento e contrato dos eventos realtime: sala por UUID, um schema por evento, sem chave duplicada (#101)."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.orm import sessionmaker

from app.agent.events import TurnEvents
from app.models import Instance
from app.realtime import events as events_module
from app.realtime import socket as socket_module
from app.realtime.event_bus import realtime_event_bus
from app.realtime.publish import publish_event
from app.realtime.socket import chat_socket_service
from tests.access_helpers import make_company, make_conversation, make_user, user_id

pytestmark = pytest.mark.asyncio

ALICE, BOB = "alice@example.com", "bob@example.com"
NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


def _instance_named(db, name: str, owner_email: str, company) -> Instance:
    """Duas Instances podem ter o mesmo `name`; só o `evolution_instance_id` é único."""
    instance = Instance(
        name=name,
        evolution_instance_id=f"evo-{uuid.uuid4()}",
        status="connected",
        is_active=True,
        owner_id=user_id(db, owner_email),
        company_id=company.id,
    )
    db.add(instance)
    db.commit()
    return instance


@pytest_asyncio.fixture
async def world(client, db, monkeypatch):
    """Alice e Bob, em Companies diferentes, com uma Instance chamada "loja" cada um e uma Conversation por Instance."""
    monkeypatch.setattr(socket_module, "SessionLocal", sessionmaker(bind=db.get_bind()))
    server = chat_socket_service.server
    emit = AsyncMock()
    monkeypatch.setattr(server, "emit", emit)
    monkeypatch.setattr(realtime_event_bus, "publish", chat_socket_service.emit_realtime_event)
    connected: list[str] = []
    companies = {ALICE: make_company(db, "Pizzaria da Alice"), BOB: make_company(db, "Pizzaria do Bob")}
    for email, company in companies.items():
        make_user(client, db, email, company=company)
    instances = {email: _instance_named(db, "loja", email, companies[email]) for email in (ALICE, BOB)}
    conversations = {email: make_conversation(db, instances[email]) for email in (ALICE, BOB)}

    async def connect(email: str) -> str:
        """Cliente real no manager do Socket.IO, que entra na sala da própria Instance e na da Conversation."""
        sid = await server.manager.connect(f"eio-{uuid.uuid4()}", "/")
        connected.append(sid)
        uid = user_id(db, email)

        async def get_session(requested_sid, namespace=None):
            return {"user_id": uid}

        monkeypatch.setattr(server, "get_session", get_session)
        handlers = server.handlers["/"]
        subscribed = await handlers["subscribe_instance"](sid, {"instanceId": instances[email].id})
        joined = await handlers["join_conversation"](
            sid, {"instanceId": instances[email].id, "conversationId": conversations[email].id}
        )
        assert subscribed == joined == {"ok": True}
        return sid

    def received_by(sid: str) -> list[tuple[str, dict]]:
        rooms = set(server.rooms(sid))
        return [(call.args[0], call.args[1]) for call in emit.await_args_list if call.kwargs["room"] in rooms]

    yield {
        "instances": instances,
        "conversations": conversations,
        "connect": connect,
        "received_by": received_by,
        "emit": emit,
    }
    for sid in connected:
        await server.manager.disconnect(sid, "/")


async def test_two_instances_with_the_same_name_in_different_companies_never_cross_events(world):
    alice_sid = await world["connect"](ALICE)
    bob_sid = await world["connect"](BOB)
    alice_instance, alice_conversation = world["instances"][ALICE], world["conversations"][ALICE]
    assert alice_instance.name == world["instances"][BOB].name

    turn = TurnEvents(instance_id=alice_instance.id, conversation_id=alice_conversation.id, request_id="req-1")
    await turn.thinking_start()
    turn.tool_started({"type": "tool_use", "id": "t1", "name": "info_empresa", "input": {}})
    await turn.flush()
    await publish_event(
        events_module.ConnectionStatusUpdate(instance_id=alice_instance.id, status="connected", evolution_state="open")
    )
    await publish_event(
        events_module.HandoffUpdated(
            instance_id=alice_instance.id,
            conversation_id=alice_conversation.id,
            change="assumed",
            human_in_loop=True,
            assigned_to="u1",
            ticket_id="t1",
            timestamp=NOW,
        )
    )

    assert [name for name, _ in world["received_by"](alice_sid)] == [
        "thinking_event",
        "tool_event",
        "connection_status_update",
        "handoff_updated",
    ]
    assert world["received_by"](bob_sid) == []


async def test_each_event_goes_to_exactly_one_room(world):
    await world["connect"](ALICE)
    instance, conversation = world["instances"][ALICE], world["conversations"][ALICE]

    await publish_event(
        events_module.ThinkingEvent(
            instance_id=instance.id, conversation_id=conversation.id, event="thinking_start"
        )
    )
    await publish_event(
        events_module.NewMessage(
            instance_id=instance.id,
            conversation_id=conversation.id,
            message_id="m1",
            content="oi",
            timestamp=NOW,
            is_outgoing=False,
            status="sent",
        )
    )

    assert [(call.args[0], call.kwargs["room"]) for call in world["emit"].await_args_list] == [
        ("thinking_event", f"conversation:{conversation.id}"),
        ("new_message", f"instance:{instance.id}"),
    ]


def _samples(instance_id: str, conversation_id: str) -> list[events_module.RealtimeEvent]:
    common = {"instance_id": instance_id}
    conv = {**common, "conversation_id": conversation_id}
    return [
        events_module.ConversationUpdated(
            **conv, contact_name="Cliente", last_message="oi", timestamp=NOW, unread_count=1, avatar=None
        ),
        events_module.NewMessage(
            **conv,
            message_id="m1",
            content="oi",
            timestamp=NOW,
            is_outgoing=False,
            status="sent",
            sender_name="Cliente",
        ),
        events_module.MessageStatusUpdate(**conv, message_id="m1", status="read"),
        events_module.ConnectionStatusUpdate(**common, status="connected", evolution_state="open"),
        events_module.QrCodeUpdate(**common, qrcode="data:image/png;base64,AAA"),
        events_module.ThinkingEvent(**conv, event="thinking_end", data={"summary": ""}),
        events_module.ToolEvent(
            **conv,
            source="whatsapp_agent",
            trace_id="tr",
            request_id="rq",
            tool_name="info_empresa",
            phase="completed",
            output_preview="ok",
        ),
        events_module.HandoffUpdated(
            **conv, change="released", human_in_loop=False, assigned_to=None, ticket_id=None, timestamp=NOW
        ),
        events_module.HumanHandoffRequested(**conv, ticket_id="t1", reason="pediu", timestamp=NOW),
    ]


async def test_every_event_reaches_the_client_with_exactly_its_schema_fields_and_no_duplicate_key(world):
    await world["connect"](ALICE)
    instance, conversation = world["instances"][ALICE], world["conversations"][ALICE]
    samples = _samples(instance.id, conversation.id)
    assert {type(sample).name for sample in samples} == set(events_module.EVENTS)

    for sample in samples:
        await publish_event(sample)

    emitted = {call.args[0]: call.args[1] for call in world["emit"].await_args_list}
    assert set(emitted) == set(events_module.EVENTS)
    for name, payload in emitted.items():
        schema = events_module.EVENTS[name]
        assert set(payload) == set(schema.model_fields), name
        assert schema.model_validate(payload).model_dump(mode="json") == payload
        # Uma grafia só: nenhuma chave em camelCase e nenhuma repetida em outra grafia.
        assert all(key == key.lower() for key in payload), name
        assert payload["instance_id"] == instance.id
        if "conversation_id" in payload:
            assert payload["conversation_id"] == conversation.id


@pytest.mark.parametrize(
    "extra",
    [{"conversationId": "x"}, {"instance_name": "loja"}, {"remote_jid": "5511@s.whatsapp.net"}],
)
async def test_payload_with_a_foreign_or_duplicate_key_is_dropped(world, extra):
    await world["connect"](ALICE)
    instance, conversation = world["instances"][ALICE], world["conversations"][ALICE]
    payload = {"instance_id": instance.id, "conversation_id": conversation.id, "event": "thinking_start", **extra}

    await chat_socket_service.emit_realtime_event({"type": "thinking_event", "payload": payload})

    world["emit"].assert_not_awaited()
