"""Eventos realtime de um Turn: `thinking_event` (`thinking_start`/`thinking_end`) e `tool_event`.

Vão para a sala da Conversation (UUID) pelos schemas de `app.realtime.events`, via
`app.realtime.publish.publish_event`. Falha ao publicar só loga: evento de UI nunca derruba um Turn.
"""

from __future__ import annotations

from typing import Literal

from app.agent.contracts import ToolUseBlock
from app.agent.tools import ToolCall
from app.realtime.events import ThinkingEvent
from app.realtime.publish import publish_event
from app.realtime.tool_events import ToolEventTracker, TrackedToolCall

EVENT_SOURCE = "whatsapp_agent"


class TurnEvents:
    """Emite os eventos de um Turn; implementa o `TurnObserver` do loop."""

    def __init__(self, *, instance_id: str, conversation_id: str, request_id: str) -> None:
        self.instance_id = instance_id
        self.conversation_id = conversation_id
        self._tracker = ToolEventTracker(
            source=EVENT_SOURCE,
            instance_id=instance_id,
            conversation_id=conversation_id,
            request_id=request_id,
        )

    async def _thinking(self, event: Literal["thinking_start", "thinking_end"], data: dict[str, str]) -> None:
        await publish_event(
            ThinkingEvent(instance_id=self.instance_id, conversation_id=self.conversation_id, event=event, data=data)
        )

    async def thinking_start(self) -> None:
        await self._thinking("thinking_start", {})

    async def thinking_end(self) -> None:
        await self._thinking("thinking_end", {"summary": ""})

    def tool_started(self, block: ToolUseBlock) -> TrackedToolCall:
        return self._tracker.start(block["name"], input_payload=block.get("input") or {})

    def tool_finished(self, handle: TrackedToolCall, call: ToolCall) -> None:
        output = call.result["content"]
        if call.is_error:
            self._tracker.fail(handle, error=output, output_payload=output)
        else:
            self._tracker.complete(handle, output_payload=output)

    async def flush(self) -> None:
        await self._tracker.flush()

