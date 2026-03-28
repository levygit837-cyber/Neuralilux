# Runtime helpers that decide when the Super Agent should call backend tools.
# Provides tool execution, JSON prompting, and tracked tool call utilities.
from __future__ import annotations

import inspect
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

import structlog

from app.core.database import get_db
from app.services.inference_service import get_inference_service
from app.services.menu_catalog_service import normalize_text
from app.services.tool_event_service import ToolEventTracker
from app.super_agents.memory.knowledge_base import KnowledgeBase
from app.super_agents.memory.session_memory import SessionMemory
from app.super_agents.prompts import TOOL_ACTION_SELECTION_PROMPT
from app.super_agents.tools.database_tool import _execute_database_query
from app.super_agents.tools.document_tool import create_document_tool
from app.super_agents.tools.menu_tool import lookup_company_menu
from app.super_agents.tools.web_tool import fetch_web_content, search_web
from app.super_agents.tools.whatsapp_tool import (
    list_company_contacts,
    read_messages_for_contact,
    resolve_company_contacts,
    send_bulk_messages_via_whatsapp,
    send_message_via_whatsapp,
)

logger = structlog.get_logger()
CONFIRM_WORDS = {
    "sim",
    "confirmar",
    "confirma",
    "pode enviar",
    "pode mandar",
    "enviar",
    "mande",
    "ok",
}
CANCEL_WORDS = {"nao", "não", "cancelar", "cancele", "parar", "pare"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tool_call(
    *,
    name: str,
    tool_input: Dict[str, Any],
    output: Dict[str, Any],
    request_id: Optional[str],
    index: int,
    status: str = "completed",
    display_name: Optional[str] = None,
    trace_id: Optional[str] = None,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
) -> Dict[str, Any]:
    started_at = started_at or _now_iso()
    finished_at = finished_at or _now_iso()
    trace_id = trace_id or f"{request_id or 'req'}:{index}:{name}"
    return {
        "name": name,
        "input": tool_input,
        "output": output,
        "status": status,
        "display_name": display_name,
        "trace_id": trace_id,
        "started_at": started_at,
        "finished_at": finished_at,
    }


def _normalize(value: Optional[str]) -> str:
    return normalize_text(value or "")


def _strip_punctuation(value: str) -> str:
    return value.strip().strip(" .,!?:;\"'")


def _currency(value: Any) -> str:
    try:
        if value is None:
            return "Preço indisponível"
        return f"R$ {float(value):.2f}".replace(".", ",")
    except Exception:
        return str(value)


def _join_lines(lines: Iterable[str]) -> str:
    return "\n".join(line for line in lines if line)


def _truncate_text(value: str, limit: int = 120) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def _safe_limit(raw: Any, default: int, *, maximum: int = 25) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(value, maximum))


def _extract_json_object(raw_text: str) -> Optional[Dict[str, Any]]:
    if not raw_text:
        return None
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


async def _run_json_prompt(prompt: str, *, max_tokens: int = 320) -> Optional[Dict[str, Any]]:
    inference_service = get_inference_service("super_agent")
    result = await inference_service.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.1,
    )
    return _extract_json_object(result.get("content", ""))


def _format_history_for_tool_planner(state: Dict[str, Any]) -> str:
    history_lines: List[str] = []
