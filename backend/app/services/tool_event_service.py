"""Helpers for emitting structured tool lifecycle events."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import structlog

from app.core.config import settings
from app.services.realtime_event_bus import realtime_event_bus

logger = structlog.get_logger()


def generate_request_id() -> str:
    return uuid4().hex


def generate_trace_id() -> str:
    return uuid4().hex


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_json_safe(value: Any) -> Any:
    if value is None:
        return None
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return str(value)


def build_tool_preview(payload: Any, limit: Optional[int] = None) -> Optional[str]:
    if payload is None:
        return None

    preview_limit = limit or settings.TOOL_EVENT_PREVIEW_LIMIT
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, default=str)

    normalized = " ".join(text.split())
    if len(normalized) <= preview_limit:
        return normalized
    return normalized[: max(1, preview_limit - 1)] + "…"


async def emit_tool_event(
    *,
    source: str,
    tool_name: str,
    phase: str,
    instance_name: str,
    conversation_id: str,
    request_id: str,
    trace_id: str,
    session_id: str | None = None,
    input_payload: Any | None = None,
    output_payload: Any | None = None,
    error: str | None = None,
    display_name: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "source": source,
        "conversation_id": conversation_id,
        "session_id": session_id,
        "trace_id": trace_id,
        "request_id": request_id,
        "tool_name": tool_name,
        "phase": phase,
        "display_name": display_name,
        "input_preview": build_tool_preview(input_payload),
        "output_preview": build_tool_preview(output_payload),
        "error": error,
        "started_at": started_at,
        "finished_at": finished_at,
    }

    if settings.TOOL_EVENT_INCLUDE_RAW_PAYLOADS:
        payload["input_payload"] = make_json_safe(input_payload)
        payload["output_payload"] = make_json_safe(output_payload)

    await realtime_event_bus.publish(
        {
            "instance_name": instance_name,
            "type": "tool_event",
            "payload": payload,
        }
    )


@dataclass(slots=True)
class TrackedToolCall:
    tool_name: str
    trace_id: str
    started_at: str
    input_payload: Any | None = None
    display_name: str | None = None


@dataclass(slots=True)
class ToolEventTracker:
    source: str
    instance_name: str
    conversation_id: str
    request_id: str
    session_id: str | None = None
    _pending_tasks: list[asyncio.Task[Any]] = field(default_factory=list)

    def _schedule(self, **kwargs: Any) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("Tool event scheduled without running loop", tool_name=kwargs.get("tool_name"))
            return

        task = loop.create_task(
            emit_tool_event(
                source=self.source,
                instance_name=self.instance_name,
                conversation_id=self.conversation_id,
                request_id=self.request_id,
                session_id=self.session_id,
                **kwargs,
            )
        )
        self._pending_tasks.append(task)

    def waiting(
        self,
        tool_name: str,
        *,
        input_payload: Any | None = None,
        display_name: str | None = None,
    ) -> str:
        trace_id = generate_trace_id()
        started_at = _now_iso()
        self._schedule(
            tool_name=tool_name,
            phase="waiting_input",
            trace_id=trace_id,
            input_payload=input_payload,
            display_name=display_name,
            started_at=started_at,
        )
        return trace_id

    def start(
        self,
        tool_name: str,
        *,
        input_payload: Any | None = None,
        display_name: str | None = None,
    ) -> TrackedToolCall:
        handle = TrackedToolCall(
            tool_name=tool_name,
            trace_id=generate_trace_id(),
            started_at=_now_iso(),
            input_payload=input_payload,
            display_name=display_name,
        )
        self._schedule(
            tool_name=tool_name,
            phase="started",
            trace_id=handle.trace_id,
            input_payload=input_payload,
            display_name=display_name,
            started_at=handle.started_at,
        )
        return handle

    def complete(
        self,
        handle: TrackedToolCall,
        *,
        output_payload: Any | None = None,
        display_name: str | None = None,
    ) -> str:
        finished_at = _now_iso()
        self._schedule(
            tool_name=handle.tool_name,
            phase="completed",
            trace_id=handle.trace_id,
            input_payload=handle.input_payload,
            output_payload=output_payload,
            display_name=display_name or handle.display_name,
            started_at=handle.started_at,
            finished_at=finished_at,
        )
        return finished_at

    def fail(
        self,
        handle: TrackedToolCall,
        *,
        error: str,
        output_payload: Any | None = None,
        display_name: str | None = None,
    ) -> str:
        finished_at = _now_iso()
        self._schedule(
            tool_name=handle.tool_name,
            phase="failed",
            trace_id=handle.trace_id,
            input_payload=handle.input_payload,
            output_payload=output_payload,
            error=error,
            display_name=display_name or handle.display_name,
            started_at=handle.started_at,
            finished_at=finished_at,
        )
        return finished_at

    async def flush(self) -> None:
        if not self._pending_tasks:
            return

        tasks = list(self._pending_tasks)
        self._pending_tasks.clear()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Tool event emission failed", error=str(result))
