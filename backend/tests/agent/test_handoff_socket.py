from unittest.mock import AsyncMock

import pytest
from pack_helpers import call, make_world, tool_named

from app.agent.core_tools import core_tools as build_core_tools
from app.models import Ticket
from app.realtime.event_bus import realtime_event_bus
from app.realtime.socket import chat_socket_service

pytestmark = pytest.mark.asyncio


@pytest.fixture
def socket_emit(monkeypatch):
    emit = AsyncMock()
    monkeypatch.setattr(chat_socket_service.server, "emit", emit)
    return emit


async def test_handoff_event_from_the_tool_reaches_the_instance_room_only(db, monkeypatch, socket_emit):
    world = make_world(db)
    published: list[dict] = []

    async def capture(event):
        published.append(event)

    monkeypatch.setattr(realtime_event_bus, "publish", capture)
    await call(
        tool_named(build_core_tools(), "transferir_atendente"), world.ctx, motivo="Pedido veio errado"
    )
    ticket = db.query(Ticket).one()

    # O evento que a Tool publica no bus é o mesmo que o consumidor do bus entrega ao socket.
    assert len(published) == 1
    await chat_socket_service.emit_realtime_event(published[0])

    socket_emit.assert_awaited_once()
    name, data = socket_emit.await_args.args
    assert name == "human_handoff_requested"
    assert socket_emit.await_args.kwargs == {"room": f"instance:{world.instance.id}"}
    assert data["instance_id"] == world.instance.id
    assert data["conversation_id"] == world.conversation.id
    assert data["ticket_id"] == ticket.id
    assert data["reason"] == "Pedido veio errado"


@pytest.mark.parametrize(
    "event",
    [
        {"type": "human_handoff_requested", "payload": {"instance_id": "inst", "reason": "x"}},
        {"type": "human_handoff_requested", "payload": {"conversation_id": "c1", "reason": "x"}},
        {"type": "evento_que_nao_existe", "payload": {"instance_id": "inst"}},
    ],
)
async def test_invalid_event_is_dropped(socket_emit, event):
    await chat_socket_service.emit_realtime_event(event)
    socket_emit.assert_not_awaited()
