from unittest.mock import AsyncMock

import pytest
from pack_helpers import call, make_world, tool_named

from app.agent import core_tools
from app.agent.core_tools import core_tools as build_core_tools
from app.models import Ticket
from app.services.socket_service import chat_socket_service

pytestmark = pytest.mark.asyncio


@pytest.fixture
def socket_emit(monkeypatch):
    emit = AsyncMock()
    monkeypatch.setattr(chat_socket_service.server, "emit", emit)
    return emit


async def test_handoff_event_from_the_tool_reaches_instance_and_conversation_rooms(db, monkeypatch, socket_emit):
    world = make_world(db)
    published: list[dict] = []

    async def capture(event):
        published.append(event)

    monkeypatch.setattr(core_tools, "publish_event", capture)
    await call(
        tool_named(build_core_tools(), "transferir_atendente"), world.ctx, motivo="Pedido veio errado"
    )
    ticket = db.query(Ticket).one()

    # O evento que a Tool publica no bus é o mesmo que o consumidor do bus entrega ao socket.
    assert len(published) == 1
    await chat_socket_service.emit_realtime_event(published[0])

    instance_room = f"instance:{world.instance.name}"
    conversation_room = f"conversation:{world.instance.name}:{world.conversation.id}"
    emitted = [(c.args[0], c.kwargs["room"]) for c in socket_emit.await_args_list]
    assert emitted == [
        ("human_handoff_requested", conversation_room),
        ("human_handoff_requested", instance_room),
    ]
    for call_ in socket_emit.await_args_list:
        data = call_.args[1]
        assert data["conversationId"] == data["conversation_id"] == world.conversation.id
        assert data["ticketId"] == data["ticket_id"] == ticket.id
        assert data["reason"] == "Pedido veio errado"


async def test_handoff_event_without_conversation_is_not_emitted(socket_emit):
    await chat_socket_service.emit_realtime_event(
        {"type": "human_handoff_requested", "instance_name": "inst", "payload": {"reason": "x"}}
    )
    socket_emit.assert_not_awaited()


async def test_handoff_event_without_instance_is_dropped_like_other_events(socket_emit):
    await chat_socket_service.emit_realtime_event(
        {"type": "human_handoff_requested", "payload": {"conversation_id": "c1", "reason": "x"}}
    )
    socket_emit.assert_not_awaited()
