"""Eventos realtime de um Turn, no formato que o frontend já consome.

`thinking` (`thinking_start`/`thinking_end`) e `tool_event` vão para a sala da
Conversation via `realtime_event_bus.publish(event)`, sempre com um único dict
(o bus não aceita kwargs). Falha ao publicar só loga: evento de UI nunca derruba
um Turn.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from app.agent.contracts import ToolUseBlock
from app.agent.tools import ToolCall
from app.services.realtime_event_bus import realtime_event_bus
from app.services.tool_event_service import ToolEventTracker, TrackedToolCall

logger = structlog.get_logger()

EVENT_SOURCE = "whatsapp_agent"


async def _publish(event: dict[str, Any]) -> None:
    try:
        await realtime_event_bus.publish(event)
    except Exception as exc:
        logger.warning("Realtime event publish failed", event_type=event.get("type"), error=str(exc))


class TurnEvents:
    """Emite os eventos de um Turn; implementa o `TurnObserver` do loop."""

    def __init__(self, *, instance_name: str, conversation_id: str, request_id: str) -> None:
        self.instance_name = instance_name
        self.conversation_id = conversation_id
        self._tracker = ToolEventTracker(
            source=EVENT_SOURCE,
            instance_name=instance_name,
            conversation_id=conversation_id,
            request_id=request_id,
        )

    async def _thinking(self, event: str, data: dict[str, Any]) -> None:
        await _publish(
            {
                "instance_name": self.instance_name,
                "type": "thinking",
                "payload": {"conversation_id": self.conversation_id, "event": event, "data": data},
            }
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


async def publish_handoff_requested(
    *,
    instance_name: str,
    conversation_id: str,
    remote_jid: str,
    ticket_id: str | None,
    reason: str,
) -> None:
    """Avisa a UI que a Conversation entrou em Handoff."""
    await _publish(
        {
            "instance_name": instance_name,
            "type": "human_handoff_requested",
            "payload": {
                "conversation_id": conversation_id,
                "remote_jid": remote_jid,
                "ticket_id": ticket_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    )
