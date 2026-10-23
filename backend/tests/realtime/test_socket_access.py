"""Socket.IO respeita o dono da Instance: join_conversation e send_message (T10, #25)."""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.orm import sessionmaker

from app.realtime import socket as socket_module
from tests.access_helpers import fake_evolution, make_conversation, make_instance, make_user, user_id

pytestmark = pytest.mark.asyncio

OWNER, OTHER, ADMIN = "dono@example.com", "outro@example.com", "admin@example.com"


@pytest_asyncio.fixture
async def world(client, db, monkeypatch):
    """Duas Instances de donos diferentes, cada uma com uma Conversation, e um superusuário."""
    monkeypatch.setattr(socket_module, "SessionLocal", sessionmaker(bind=db.get_bind()))
    connected: list[str] = []
    for email, superuser in ((OWNER, False), (OTHER, False), (ADMIN, True)):
        make_user(client, db, email, superuser=superuser)
    mine = make_instance(db, "inst-dono", OWNER)
    theirs = make_instance(db, "inst-outro", OTHER)
    yield {
        "mine": mine,
        "theirs": theirs,
        "mine_conversation": make_conversation(db, mine),
        "theirs_conversation": make_conversation(db, theirs),
        "evolution": fake_evolution(monkeypatch),
        "db": db,
        "connected": connected,
    }
    # O manager do Socket.IO é um singleton do módulo: não deixa conexões ou salas para o próximo teste.
    for sid in connected:
        await socket_module.chat_socket_service.server.manager.disconnect(sid, "/")


async def _connect(world, monkeypatch, email: str) -> tuple[str, object]:
    """Conecta um cliente no manager real do Socket.IO; o handler lê o usuário da sessão."""
    server = socket_module.chat_socket_service.server
    sid = await server.manager.connect(f"eio-{uuid.uuid4()}", "/")
    world["connected"].append(sid)
    uid = user_id(world["db"], email)

    async def get_session(requested_sid, namespace=None):
        return {"user_id": uid}

    monkeypatch.setattr(server, "get_session", get_session)
    return sid, server


def _handler(name: str):
    return socket_module.chat_socket_service.server.handlers["/"][name]


def _rooms(server, sid) -> list[str]:
    return [room for room in server.rooms(sid) if room != sid]


@pytest.mark.parametrize("email,instance_key,conversation_key,allowed", [
    (OWNER, "mine", "mine_conversation", True),
    (ADMIN, "theirs", "theirs_conversation", True),
    (OTHER, "mine", "mine_conversation", False),
    (OWNER, "theirs", "theirs_conversation", False),
])
async def test_join_conversation_follows_the_instance_owner(world, monkeypatch, email, instance_key, conversation_key, allowed):
    sid, server = await _connect(world, monkeypatch, email)
    instance = world[instance_key]
    conversation = world[conversation_key]

    result = await _handler("join_conversation")(
        sid, {"instanceName": instance.name, "conversationId": conversation.id}
    )

    expected_room = f"conversation:{instance.name}:{conversation.id}"
    assert result == {"ok": allowed}
    assert _rooms(server, sid) == ([expected_room] if allowed else [])


async def test_join_conversation_of_an_unknown_instance_is_denied(world, monkeypatch):
    sid, server = await _connect(world, monkeypatch, OWNER)

    result = await _handler("join_conversation")(sid, {"instanceName": "nao-existe", "conversationId": "c1"})

    assert result == {"ok": False}
    assert _rooms(server, sid) == []


@pytest.mark.parametrize("email,instance_key,conversation_key,allowed", [
    (OWNER, "mine", "mine_conversation", True),
    (ADMIN, "theirs", "theirs_conversation", True),
    (OTHER, "mine", "mine_conversation", False),
    (OWNER, "theirs", "theirs_conversation", False),
])
async def test_send_message_follows_the_instance_owner(world, monkeypatch, email, instance_key, conversation_key, allowed):
    sid, _ = await _connect(world, monkeypatch, email)
    instance = world[instance_key]
    conversation = world[conversation_key]
    send = world["evolution"]["send_text_message"]

    result = await _handler("send_message")(
        sid, {"instanceName": instance.name, "conversationId": conversation.id, "content": "oi"}
    )

    if allowed:
        assert result == {"ok": True, "messageId": "wamid-1"}
        send.assert_awaited_once_with(instance.evolution_instance_id, conversation.remote_jid, "oi")
    else:
        assert result == {"ok": False}
        send.assert_not_called()


async def test_send_message_accepts_the_remote_jid_as_conversation_reference(world, monkeypatch):
    sid, _ = await _connect(world, monkeypatch, OWNER)
    conversation = world["mine_conversation"]
    send = world["evolution"]["send_text_message"]

    result = await _handler("send_message")(
        sid, {"instanceName": "inst-dono", "conversationId": conversation.remote_jid, "content": "oi"}
    )

    assert result["ok"] is True
    send.assert_awaited_once_with("inst-dono", conversation.remote_jid, "oi")


async def test_send_message_refuses_a_conversation_of_another_instance_even_for_the_owner(world, monkeypatch):
    # O dono usa a própria Instance, mas aponta para a Conversation (ou o JID) de outra Instance.
    sid, _ = await _connect(world, monkeypatch, OWNER)
    send = world["evolution"]["send_text_message"]
    foreign = world["theirs_conversation"]

    by_id = await _handler("send_message")(
        sid, {"instanceName": "inst-dono", "conversationId": foreign.id, "content": "oi"}
    )
    by_jid = await _handler("send_message")(
        sid, {"instanceName": "inst-dono", "conversationId": foreign.remote_jid, "content": "oi"}
    )

    assert by_id == by_jid == {"ok": False}
    send.assert_not_called()


async def test_superuser_cannot_send_to_a_conversation_outside_the_named_instance(world, monkeypatch):
    sid, _ = await _connect(world, monkeypatch, ADMIN)
    send = world["evolution"]["send_text_message"]

    result = await _handler("send_message")(
        sid, {"instanceName": "inst-dono", "conversationId": world["theirs_conversation"].id, "content": "oi"}
    )

    assert result == {"ok": False}
    send.assert_not_called()


async def test_leaving_never_needs_access(world, monkeypatch):
    sid, server = await _connect(world, monkeypatch, OWNER)
    joined = await _handler("join_conversation")(
        sid, {"instanceName": "inst-dono", "conversationId": world["mine_conversation"].id}
    )
    assert joined == {"ok": True}

    left = await _handler("leave_conversation")(
        sid, {"instanceName": "inst-dono", "conversationId": world["mine_conversation"].id}
    )

    assert left == {"ok": True}
    assert _rooms(server, sid) == []
