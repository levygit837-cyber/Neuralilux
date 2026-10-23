"""Eventos de um Turn, do `TurnEvents` até as salas do Socket.IO que o frontend escuta."""
from unittest.mock import AsyncMock

import pytest

from app.agent.events import TurnEvents
from app.agent.tools import ToolCall
from app.realtime.event_bus import realtime_event_bus
from app.realtime.socket import chat_socket_service

INSTANCE = "company-123"
CONVERSATION = "5511999990001@s.whatsapp.net"


@pytest.fixture
def socket(monkeypatch):
    """Liga o bus ao socket service (como o API faz) e captura o que sai para o cliente."""
    emit = AsyncMock()
    monkeypatch.setattr(chat_socket_service.server, "emit", emit)
    monkeypatch.setattr(realtime_event_bus, "publish", chat_socket_service.emit_realtime_event)

    def emitted():
        return [(call.args[0], call.args[1], call.kwargs["room"]) for call in emit.await_args_list]

    return emitted


def _events() -> TurnEvents:
    return TurnEvents(instance_name=INSTANCE, conversation_id=CONVERSATION, request_id="req-1")


@pytest.mark.asyncio
async def test_thinking_reaches_the_conversation_room_and_the_instance_room(socket):
    events = _events()

    await events.thinking_start()
    await events.thinking_end()

    emitted = socket()
    assert [(name, room) for name, _payload, room in emitted] == [
        ("thinking_event", f"conversation:{INSTANCE}:{CONVERSATION}"),
        ("thinking_event", f"instance:{INSTANCE}"),
        ("thinking_event", f"conversation:{INSTANCE}:{CONVERSATION}"),
        ("thinking_event", f"instance:{INSTANCE}"),
    ]
    start, end = emitted[0][1], emitted[2][1]
    assert (start["event"], start["conversationId"], start["data"]) == ("thinking_start", CONVERSATION, {})
    assert (end["event"], end["conversationId"]) == ("thinking_end", CONVERSATION)


@pytest.mark.asyncio
async def test_tool_call_reaches_the_client_as_started_then_completed_with_one_trace(socket):
    events = _events()
    block = {"type": "tool_use", "id": "toolu_1", "name": "buscar_cardapio", "input": {"consulta": "pizza"}}
    handle = events.tool_started(block)
    events.tool_finished(
        handle,
        ToolCall(
            name="buscar_cardapio",
            input={"consulta": "pizza"},
            result={"type": "tool_result", "tool_use_id": "toolu_1", "content": "Pizza Toscana R$ 45,90"},
        ),
    )

    await events.flush()

    tool_events = [payload for name, payload, _room in socket() if name == "tool_event"]
    assert len({payload["traceId"] for payload in tool_events}) == 1
    assert [payload["phase"] for payload in tool_events][-1] == "completed"
    assert all(payload["conversationId"] == CONVERSATION and payload["toolName"] == "buscar_cardapio" for payload in tool_events)


@pytest.mark.asyncio
async def test_failed_tool_reaches_the_client_with_its_error(socket):
    events = _events()
    handle = events.tool_started({"type": "tool_use", "id": "t2", "name": "criar_pedido", "input": {}})
    events.tool_finished(
        handle,
        ToolCall(
            name="criar_pedido",
            input={},
            result={"type": "tool_result", "tool_use_id": "t2", "content": "estoque insuficiente", "is_error": True},
        ),
    )

    await events.flush()

    last = [payload for name, payload, _room in socket() if name == "tool_event"][-1]
    assert last["phase"] == "failed"
    assert "estoque insuficiente" in last["error"]
