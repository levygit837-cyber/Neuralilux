"""Eventos realtime de um Turn: thinking_event e tool_event, publicados no bus com o payload canônico."""

from unittest.mock import AsyncMock

import pytest

from app.agent.events import TurnEvents
from app.agent.tools import ToolCall
from app.realtime.event_bus import realtime_event_bus


@pytest.fixture
def published(monkeypatch):
    bus = AsyncMock()
    monkeypatch.setattr(realtime_event_bus, "publish", bus)

    def events():
        # `publish(event)` recebe um único dict posicional; kwargs dariam TypeError no bus real.
        for call in bus.await_args_list:
            assert call.kwargs == {}
        return [call.args[0] for call in bus.await_args_list]

    return events


def _events():
    return TurnEvents(instance_id="inst-1", conversation_id="conv-1", request_id="req-1")


@pytest.mark.asyncio
async def test_thinking_start_e_end_na_sala_da_conversa(published):
    events = _events()

    await events.thinking_start()
    await events.thinking_end()

    assert published() == [
        {
            "type": "thinking_event",
            "payload": {
                "instance_id": "inst-1",
                "conversation_id": "conv-1",
                "event": "thinking_start",
                "data": {},
            },
        },
        {
            "type": "thinking_event",
            "payload": {
                "instance_id": "inst-1",
                "conversation_id": "conv-1",
                "event": "thinking_end",
                "data": {"summary": ""},
            },
        },
    ]


@pytest.mark.asyncio
async def test_tool_concluida_emite_started_e_completed_com_o_mesmo_trace(published):
    events = _events()
    block = {"type": "tool_use", "id": "toolu_1", "name": "buscar_cardapio", "input": {"consulta": "pizza"}}
    call = ToolCall(
        name="buscar_cardapio",
        input={"consulta": "pizza"},
        result={"type": "tool_result", "tool_use_id": "toolu_1", "content": "Pizza Toscana R$ 45,90"},
    )

    handle = events.tool_started(block)
    events.tool_finished(handle, call)
    await events.flush()

    started, completed = published()
    assert started["type"] == completed["type"] == "tool_event"
    assert started["payload"]["instance_id"] == "inst-1"
    assert started["payload"]["phase"] == "started"
    assert started["payload"]["source"] == "whatsapp_agent"
    assert started["payload"]["conversation_id"] == "conv-1"
    assert started["payload"]["tool_name"] == "buscar_cardapio"
    assert started["payload"]["input_preview"] == '{"consulta": "pizza"}'
    assert completed["payload"]["phase"] == "completed"
    assert completed["payload"]["output_preview"] == "Pizza Toscana R$ 45,90"
    assert completed["payload"]["trace_id"] == started["payload"]["trace_id"]


@pytest.mark.asyncio
async def test_tool_com_erro_emite_failed(published):
    events = _events()
    block = {"type": "tool_use", "id": "toolu_1", "name": "gerenciar_pedido", "input": {}}
    call = ToolCall(
        name="gerenciar_pedido",
        input={},
        result={"type": "tool_result", "tool_use_id": "toolu_1", "content": "Item indisponível", "is_error": True},
    )

    events.tool_finished(events.tool_started(block), call)
    await events.flush()

    failed = published()[-1]["payload"]
    assert failed["phase"] == "failed"
    assert failed["error"] == "Item indisponível"


@pytest.mark.asyncio
async def test_falha_do_bus_nao_derruba_o_turn(monkeypatch):
    monkeypatch.setattr(realtime_event_bus, "publish", AsyncMock(side_effect=ConnectionError("redis fora")))
    events = _events()

    await events.thinking_start()
    events.tool_started({"type": "tool_use", "id": "t", "name": "info_empresa", "input": {}})
    await events.flush()

