# Runtime helpers that decide when the Super Agent should call backend tools.
# Provides tool execution, JSON prompting, and tracked tool call utilities.
from __future__ import annotations

import inspect
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import structlog

from app.core.database import get_db
from app.services.inference_service import get_inference_service
from app.services.menu_catalog_service import normalize_text
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
inference_service = get_inference_service("super_agent")

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
    result = await inference_service.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.1,
    )
    return _extract_json_object(result.get("content", ""))


def _message_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        chunks: List[str] = []
        for item in value:
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(str(item.get("text") or ""))
            elif isinstance(item, str):
                chunks.append(item)
        return " ".join(chunk for chunk in chunks if chunk)
    return str(value or "")


def _message_role(message: Any) -> str:
    role = getattr(message, "type", None) or getattr(message, "role", None)
    if role:
        return str(role)
    if isinstance(message, dict):
        return str(message.get("role") or "unknown")
    return "unknown"


def _format_history_for_tool_planner(state: Dict[str, Any]) -> str:
    history_lines: List[str] = []
    messages = list(state.get("messages") or [])
    for message in messages[-8:]:
        role = _message_role(message)
        content = _message_content(getattr(message, "content", None) if not isinstance(message, dict) else message.get("content"))
        content = _truncate_text(content, 240)
        if not content:
            continue
        history_lines.append(f"{role}: {content}")
    return _join_lines(history_lines) or "Sem histórico recente."


def _matches_any(text: str, options: set[str]) -> bool:
    normalized = _normalize(text)
    return any(option in normalized for option in options)


def _empty_result(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "response": None,
        "thinking_content": state.get("thinking_content"),
        "tool_calls": [],
        "pending_action": None,
        "skip_model_response": False,
        "db_query_result": None,
        "whatsapp_result": None,
        "menu_result": None,
        "web_result": None,
        "knowledge_result": None,
        "document_id": None,
        "document_type": None,
        "document_content": None,
    }


def _with_thinking(state: Dict[str, Any], extra: str) -> str:
    return _join_lines(
        [
            (state.get("thinking_content") or "").strip(),
            extra.strip(),
        ]
    )


def _contact_display_name(contact: Dict[str, Any]) -> str:
    return (
        contact.get("display_name")
        or contact.get("name")
        or contact.get("push_name")
        or contact.get("phone_number")
        or contact.get("remote_jid")
        or "Contato"
    )


def _format_contact_options(contacts: List[Dict[str, Any]]) -> str:
    lines = ["Encontrei mais de um contato. Escolha uma opção:"]
    for index, contact in enumerate(contacts, start=1):
        phone = contact.get("phone_number") or contact.get("remote_jid") or "sem número"
        lines.append(f"{index}. {_contact_display_name(contact)} ({phone})")
    return _join_lines(lines)


def _select_contact_from_reply(reply: str, contacts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    normalized_reply = _normalize(reply)
    if normalized_reply.isdigit():
        index = int(normalized_reply) - 1
        if 0 <= index < len(contacts):
            return contacts[index]

    exact_matches = [
        contact
        for contact in contacts
        if _normalize(_contact_display_name(contact)) == normalized_reply
        or _normalize(contact.get("phone_number")) == normalized_reply
        or _normalize(contact.get("remote_jid")) == normalized_reply
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]

    partial_matches = [
        contact
        for contact in contacts
        if normalized_reply
        and normalized_reply in _normalize(_contact_display_name(contact))
    ]
    if len(partial_matches) == 1:
        return partial_matches[0]

    return None


async def _load_pending_action(session_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not session_id:
        return None

    db = None
    try:
        db_gen = get_db()
        db = next(db_gen)
        messages = await SessionMemory.get_recent_messages(db=db, session_id=session_id, limit=12)
        for message in reversed(messages):
            extra_data = message.get("extra_data") or {}
            pending_action = extra_data.get("pending_action")
            if pending_action:
                return pending_action
        return None
    finally:
        if db is not None:
            db.close()


def _format_message_history(contact_name: str, payload: Dict[str, Any]) -> str:
    messages = payload.get("messages") or []
    if not messages:
        return f"Não encontrei mensagens recentes com {contact_name}."

    lines = [f"Mensagens recentes com {contact_name}:"]
    for message in messages[:10]:
        author = "Você" if message.get("from_me") else contact_name
        content = _truncate_text(message.get("content") or "[sem texto]", 240)
        lines.append(f"- {author}: {content}")
    return _join_lines(lines)


def _format_menu_response(payload: Dict[str, Any]) -> str:
    if not payload.get("catalog"):
        return "Não encontrei um cardápio ativo para essa empresa."

    items = payload.get("items") or []
    categories = payload.get("categories") or []
    category = payload.get("category")
    query = payload.get("query")

    if category:
        lines = [f"Filtrando pela categoria {category} para te mostrar o item certo:"]
        if not items:
            lines.append("Não encontrei itens nessa categoria.")
        for item in items[:8]:
            price = _currency(item.get("price"))
            lines.append(f"- {item.get('name')}: {price}")
        return _join_lines(lines)

    if query:
        lines = [f"Encontrei estes itens relacionados a '{query}':"]
        if not items:
            lines.append("Não achei itens com esse termo.")
        for item in items[:8]:
            category_name = item.get("category_name") or "Categoria"
            price = _currency(item.get("price"))
            lines.append(f"- {item.get('name')} ({category_name}) - {price}")
        return _join_lines(lines)

    lines = ["Categorias disponíveis no cardápio:"]
    for category_payload in categories[:10]:
        lines.append(
            f"- {category_payload.get('name')} ({category_payload.get('item_count', 0)} itens)"
        )
    lines.append("Se quiser, eu posso filtrar uma categoria ou procurar um item específico.")
    return _join_lines(lines)


def _database_item_label(item: Dict[str, Any]) -> str:
    for key in ("display_name", "name", "title", "phone_number", "remote_jid", "id"):
        value = item.get(key)
        if value:
            return str(value)
    return json.dumps(item, ensure_ascii=False, default=str)


def _format_database_response(payload: Dict[str, Any]) -> str:
    if payload.get("error"):
        return f"Não consegui concluir a consulta: {payload['error']}"

    if "aggregates" in payload:
        lines = [f"Agrupamentos em {payload.get('table')}:"]
        for row in payload.get("aggregates") or []:
            label = ", ".join(f"{key}={value}" for key, value in row.items() if key != "count")
            lines.append(f"- {label}: {row.get('count', 0)}")
        return _join_lines(lines)

    if "count" in payload and "items" not in payload:
        return f"Encontrei {payload.get('count', 0)} registro(s) em {payload.get('table')}."

    items = payload.get("items") or []
    if not items:
        return f"Não encontrei resultados em {payload.get('table')}."

    lines = [f"Encontrei {len(items)} resultado(s) em {payload.get('table')}:"]
    for item in items[:10]:
        lines.append(f"- {_database_item_label(item)}")
    return _join_lines(lines)


def _format_web_search_response(payload: Dict[str, Any]) -> str:
    results = payload.get("results") or []
    query = payload.get("query") or "sua busca"
    if not results:
        return f"Não encontrei resultados públicos para '{query}'."

    lines = [f"Encontrei {len(results)} resultado(s) para '{query}':"]
    for result in results[:5]:
        title = result.get("title") or "Sem título"
        url = result.get("url") or ""
        lines.append(f"- {title} {url}".strip())
    return _join_lines(lines)


def _format_web_fetch_response(payload: Dict[str, Any]) -> str:
    if payload.get("error"):
        return f"Não consegui abrir a URL: {payload['error']}"
    title = payload.get("title") or payload.get("url") or "Conteúdo web"
    content = _truncate_text(payload.get("content") or "", 500)
    return _join_lines([title, content])


def _format_knowledge_response(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "Não encontrei conhecimento salvo com esse tema."
    lines = ["Encontrei estes conhecimentos relacionados:"]
    for item in items[:5]:
        lines.append(f"- {item.get('key')}: {_truncate_text(item.get('value') or '', 180)}")
    return _join_lines(lines)


def _parse_tool_output(raw_output: Any) -> Dict[str, Any]:
    if isinstance(raw_output, dict):
        return raw_output
    if isinstance(raw_output, str):
        try:
            parsed = json.loads(raw_output)
            if isinstance(parsed, dict):
                return parsed
            return {"value": parsed}
        except json.JSONDecodeError:
            return {"value": raw_output}
    return {"value": raw_output}


async def _invoke_document_tool(payload: Dict[str, Any]) -> Dict[str, Any]:
    if hasattr(create_document_tool, "ainvoke"):
        raw_output = await create_document_tool.ainvoke(payload)
    elif hasattr(create_document_tool, "invoke"):
        raw_output = create_document_tool.invoke(payload)
    else:
        raw_output = create_document_tool(**payload)

    if inspect.isawaitable(raw_output):
        raw_output = await raw_output
    return _parse_tool_output(raw_output)


async def _resolve_tool_plan(state: Dict[str, Any]) -> Dict[str, Any]:
    tool_plan = state.get("tool_plan")
    if isinstance(tool_plan, dict) and tool_plan.get("mode"):
        return tool_plan

    current_message = state.get("current_message") or ""
    prompt = (
        TOOL_ACTION_SELECTION_PROMPT
        .replace("{intent}", state.get("intent") or "general")
        .replace("{history}", _format_history_for_tool_planner(state))
        .replace("{message}", current_message)
    )
    planned = await _run_json_prompt(prompt)
    if isinstance(planned, dict) and planned.get("mode"):
        return planned

    normalized_message = _normalize(current_message)
    if any(keyword in normalized_message for keyword in {"cardapio", "cardápio", "menu"}):
        return {"mode": "menu_lookup"}
    if "bebida" in normalized_message:
        return {"mode": "menu_lookup", "menu_category": "Bebidas", "menu_limit": 6}
    if "sopa" in normalized_message:
        return {"mode": "menu_lookup", "menu_category": "Sopas", "menu_limit": 6}
    if re.search(r"https?://", current_message):
        return {"mode": "web_fetch", "web_url": re.search(r"https?://\S+", current_message).group(0)}
    if "pesquise" in normalized_message or "procure na internet" in normalized_message:
        return {"mode": "web_search", "web_query": current_message}
    return {"mode": "none"}


def _confirmation_response(recipients: List[Dict[str, Any]], message_text: str) -> str:
    lines = [f"Vou enviar esta mensagem: '{message_text}'", "Destinatários:"]
    for recipient in recipients[:10]:
        lines.append(f"- {_contact_display_name(recipient)}")
    if len(recipients) > 10:
        lines.append(f"- e mais {len(recipients) - 10} contato(s)")
    lines.append("Se estiver certo, responda com 'sim'.")
    return _join_lines(lines)


async def _handle_confirm_send(
    state: Dict[str, Any],
    pending_action: Dict[str, Any],
) -> Dict[str, Any]:
    current_message = state.get("current_message") or ""
    recipients = list(pending_action.get("recipients") or [])
    message_text = pending_action.get("message") or ""
    request_id = state.get("request_id")

    if _matches_any(current_message, CANCEL_WORDS):
        return {
            **_empty_result(state),
            "response": "Envio cancelado.",
            "thinking_content": _with_thinking(state, "O usuário cancelou o envio pendente."),
            "skip_model_response": True,
        }

    if not _matches_any(current_message, CONFIRM_WORDS):
        return {
            **_empty_result(state),
            "response": _confirmation_response(recipients, message_text),
            "thinking_content": _with_thinking(state, "Aguardando confirmação explícita para enviar mensagem."),
            "pending_action": pending_action,
            "skip_model_response": True,
        }

    tool_calls: List[Dict[str, Any]] = []
    if len(recipients) == 1:
        recipient = recipients[0]
        tool_input = {
            "instance_name": recipient.get("instance_name"),
            "remote_jid": recipient.get("remote_jid"),
            "message": message_text,
        }
        output = send_message_via_whatsapp(**tool_input)
        tool_calls.append(
            _tool_call(
                name="whatsapp_send_message_tool",
                tool_input=tool_input,
                output=output,
                request_id=request_id,
                index=0,
                display_name="Envio WhatsApp",
            )
        )
        response = f"Mensagem enviada para {_contact_display_name(recipient)}."
        whatsapp_result = output
    else:
        output = send_bulk_messages_via_whatsapp(recipients=recipients, message=message_text)
        tool_calls.append(
            _tool_call(
                name="whatsapp_send_bulk_tool",
                tool_input={"recipients": recipients, "message": message_text},
                output=output,
                request_id=request_id,
                index=0,
                display_name="Envio em massa",
            )
        )
        response = (
            f"Envio concluído para {output.get('success_count', 0)} de "
            f"{output.get('total', len(recipients))} contato(s)."
        )
        whatsapp_result = output

    return {
        **_empty_result(state),
        "response": response,
        "thinking_content": _with_thinking(state, "Envio confirmado e executado via WhatsApp."),
        "tool_calls": tool_calls,
        "whatsapp_result": whatsapp_result,
        "skip_model_response": True,
    }


async def _handle_select_contact(
    state: Dict[str, Any],
    pending_action: Dict[str, Any],
) -> Dict[str, Any]:
    contacts = list(pending_action.get("contacts") or [])
    selected_contact = _select_contact_from_reply(state.get("current_message") or "", contacts)
    if not selected_contact:
        return {
            **_empty_result(state),
            "response": _format_contact_options(contacts),
            "thinking_content": _with_thinking(state, "Ainda preciso que o usuário escolha um contato válido."),
            "pending_action": pending_action,
            "skip_model_response": True,
        }

    mode = pending_action.get("mode")
    request_id = state.get("request_id")
    contact_name = _contact_display_name(selected_contact)

    if mode == "read_messages":
        tool_input = {
            "instance_name": selected_contact.get("instance_name"),
            "remote_jid": selected_contact.get("remote_jid"),
            "limit": pending_action.get("limit", 20),
        }
        output = read_messages_for_contact(**tool_input)
        return {
            **_empty_result(state),
            "response": _format_message_history(contact_name, output),
            "thinking_content": _with_thinking(state, f"Histórico carregado para o contato {contact_name}."),
            "tool_calls": [
                _tool_call(
                    name="whatsapp_read_messages_tool",
                    tool_input=tool_input,
                    output=output,
                    request_id=request_id,
                    index=0,
                    display_name="Leitura de mensagens",
                )
            ],
            "whatsapp_result": output,
            "skip_model_response": True,
        }

    if mode in {"send_message", "whatsapp_send"}:
        message_text = pending_action.get("message") or ""
        new_pending_action = {
            "type": "confirm_send",
            "message": message_text,
            "recipients": [selected_contact],
            "company_id": state.get("company_id"),
        }
        return {
            **_empty_result(state),
            "response": _confirmation_response([selected_contact], message_text),
            "thinking_content": _with_thinking(state, f"Contato {contact_name} selecionado para envio."),
            "pending_action": new_pending_action,
            "skip_model_response": True,
        }

    return {
        **_empty_result(state),
        "response": f"Contato {_contact_display_name(selected_contact)} selecionado.",
        "thinking_content": _with_thinking(state, "Seleção de contato concluída."),
        "skip_model_response": True,
    }


async def _handle_pending_action(
    state: Dict[str, Any],
    pending_action: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    pending_type = pending_action.get("type")
    if pending_type == "confirm_send":
        return await _handle_confirm_send(state, pending_action)
    if pending_type == "select_contact":
        return await _handle_select_contact(state, pending_action)
    return None


async def execute_tools_for_state(state: Dict[str, Any]) -> Dict[str, Any]:
    pending_action = await _load_pending_action(state.get("session_id"))
    if pending_action:
        handled_pending_action = await _handle_pending_action(state, pending_action)
        if handled_pending_action is not None:
            return handled_pending_action

    tool_plan = await _resolve_tool_plan(state)
    mode = (tool_plan.get("mode") or "none").strip().lower()
    request_id = state.get("request_id")
    company_id = state.get("company_id")

    if mode == "none":
        return {
            **_empty_result(state),
            "thinking_content": _with_thinking(state, "Nenhuma ferramenta foi necessária para esta etapa."),
        }

    if mode == "whatsapp_send":
        recipient_scope = (tool_plan.get("recipient_scope") or "specific").strip().lower()
        message_text = _strip_punctuation(tool_plan.get("message_text") or "")
        if not message_text:
            message_text = _strip_punctuation(state.get("current_message") or "")

        if recipient_scope == "all":
            recipients = list_company_contacts(
                company_id=company_id,
                limit=_safe_limit(tool_plan.get("recipient_limit"), 50, maximum=200),
            )
            if not recipients:
                return {
                    **_empty_result(state),
                    "response": "Não encontrei contatos ativos para enviar a mensagem.",
                    "thinking_content": _with_thinking(state, "Nenhum contato disponível para envio em massa."),
                    "skip_model_response": True,
                }
            pending = {
                "type": "confirm_send",
                "message": message_text,
                "recipients": recipients,
                "company_id": company_id,
            }
            return {
                **_empty_result(state),
                "response": _confirmation_response(recipients, message_text),
                "thinking_content": _with_thinking(state, "Preparei um envio em massa e pedi confirmação."),
                "pending_action": pending,
                "tool_calls": [
                    _tool_call(
                        name="whatsapp_list_contacts_tool",
                        tool_input={"company_id": company_id, "limit": len(recipients)},
                        output={"contacts": recipients, "count": len(recipients)},
                        request_id=request_id,
                        index=0,
                        display_name="Listagem de contatos",
                    )
                ],
                "skip_model_response": True,
            }

        recipient_names = list(tool_plan.get("recipient_names") or [])
        if not recipient_names and tool_plan.get("contact_query"):
            recipient_names = [tool_plan.get("contact_query")]

        if not recipient_names:
            return {
                **_empty_result(state),
                "response": "Preciso saber para qual contato devo enviar a mensagem.",
                "thinking_content": _with_thinking(state, "Faltou identificar o destinatário do envio."),
                "skip_model_response": True,
            }

        all_recipients: List[Dict[str, Any]] = []
        tool_calls: List[Dict[str, Any]] = []
        for index, recipient_name in enumerate(recipient_names):
            resolved_contacts = resolve_company_contacts(
                company_id=company_id,
                query=recipient_name,
                limit=_safe_limit(tool_plan.get("recipient_limit"), 10),
            )
            tool_calls.append(
                _tool_call(
                    name="whatsapp_resolve_contacts_tool",
                    tool_input={"company_id": company_id, "query": recipient_name},
                    output={"contacts": resolved_contacts, "count": len(resolved_contacts)},
                    request_id=request_id,
                    index=index,
                    display_name="Resolução de contatos",
                )
            )
            if len(recipient_names) == 1 and len(resolved_contacts) > 1:
                pending = {
                    "type": "select_contact",
                    "mode": "send_message",
                    "message": message_text,
                    "contacts": resolved_contacts,
                    "original_query": recipient_name,
                }
                return {
                    **_empty_result(state),
                    "response": _format_contact_options(resolved_contacts),
                    "thinking_content": _with_thinking(state, "Preciso que o usuário escolha o contato correto antes do envio."),
                    "pending_action": pending,
                    "tool_calls": tool_calls,
                    "skip_model_response": True,
                }
            if resolved_contacts:
                all_recipients.extend(resolved_contacts[:1] if len(recipient_names) > 1 else resolved_contacts)

        unique_recipients: List[Dict[str, Any]] = []
        seen_contacts: set[tuple[str, str]] = set()
        for recipient in all_recipients:
            key = (
                recipient.get("instance_name") or "",
                recipient.get("remote_jid") or "",
            )
            if key in seen_contacts:
                continue
            seen_contacts.add(key)
            unique_recipients.append(recipient)

        if not unique_recipients:
            return {
                **_empty_result(state),
                "response": "Não encontrei os contatos informados para enviar a mensagem.",
                "thinking_content": _with_thinking(state, "A resolução de contatos não encontrou destinatários válidos."),
                "tool_calls": tool_calls,
                "skip_model_response": True,
            }

        pending = {
            "type": "confirm_send",
            "message": message_text,
            "recipients": unique_recipients,
            "company_id": company_id,
        }
        return {
            **_empty_result(state),
            "response": _confirmation_response(unique_recipients, message_text),
            "thinking_content": _with_thinking(state, "Preparei o envio para contatos específicos e pedi confirmação."),
            "pending_action": pending,
            "tool_calls": tool_calls,
            "skip_model_response": True,
        }

    if mode == "whatsapp_read_messages":
        contact_query = tool_plan.get("contact_query") or state.get("current_message") or ""
        limit = _safe_limit(tool_plan.get("limit"), 20, maximum=50)
        resolved_contacts = resolve_company_contacts(
            company_id=company_id,
            query=contact_query,
            limit=_safe_limit(tool_plan.get("contact_limit"), 10),
        )
        resolve_call = _tool_call(
            name="whatsapp_resolve_contacts_tool",
            tool_input={"company_id": company_id, "query": contact_query},
            output={"contacts": resolved_contacts, "count": len(resolved_contacts)},
            request_id=request_id,
            index=0,
            display_name="Resolução de contatos",
        )
        if not resolved_contacts:
            return {
                **_empty_result(state),
                "response": f"Não encontrei nenhum contato para '{contact_query}'.",
                "thinking_content": _with_thinking(state, "A busca de contatos não retornou resultados."),
                "tool_calls": [resolve_call],
                "skip_model_response": True,
            }
        if len(resolved_contacts) > 1:
            pending = {
                "type": "select_contact",
                "mode": "read_messages",
                "contacts": resolved_contacts,
                "original_query": contact_query,
                "limit": limit,
            }
            return {
                **_empty_result(state),
                "response": _format_contact_options(resolved_contacts),
                "thinking_content": _with_thinking(state, "Encontrei múltiplos contatos e preciso da escolha do usuário."),
                "pending_action": pending,
                "tool_calls": [resolve_call],
                "skip_model_response": True,
            }

        selected_contact = resolved_contacts[0]
        read_input = {
            "instance_name": selected_contact.get("instance_name"),
            "remote_jid": selected_contact.get("remote_jid"),
            "limit": limit,
        }
        read_output = read_messages_for_contact(**read_input)
        return {
            **_empty_result(state),
            "response": _format_message_history(_contact_display_name(selected_contact), read_output),
            "thinking_content": _with_thinking(state, f"Li o histórico recente de {_contact_display_name(selected_contact)}."),
            "tool_calls": [
                resolve_call,
                _tool_call(
                    name="whatsapp_read_messages_tool",
                    tool_input=read_input,
                    output=read_output,
                    request_id=request_id,
                    index=1,
                    display_name="Leitura de mensagens",
                ),
            ],
            "whatsapp_result": read_output,
            "skip_model_response": True,
        }

    if mode == "whatsapp_list_contacts":
        search_term = tool_plan.get("contact_query") or tool_plan.get("search") or ""
        contacts = list_company_contacts(
            company_id=company_id,
            search=search_term,
            limit=_safe_limit(tool_plan.get("limit"), 10),
        )
        lines = ["Contatos encontrados:"]
        for contact in contacts[:10]:
            lines.append(f"- {_contact_display_name(contact)}")
        if len(lines) == 1:
            lines.append("Nenhum contato encontrado.")
        payload = {"contacts": contacts, "count": len(contacts)}
        return {
            **_empty_result(state),
            "response": _join_lines(lines),
            "thinking_content": _with_thinking(state, "Listei os contatos disponíveis."),
            "tool_calls": [
                _tool_call(
                    name="whatsapp_list_contacts_tool",
                    tool_input={"company_id": company_id, "search": search_term},
                    output=payload,
                    request_id=request_id,
                    index=0,
                    display_name="Listagem de contatos",
                )
            ],
            "whatsapp_result": payload,
            "skip_model_response": True,
        }

    if mode == "web_search":
        query = tool_plan.get("web_query") or state.get("current_message") or ""
        payload = search_web(query=query, max_results=_safe_limit(tool_plan.get("web_limit"), 5, maximum=10))
        return {
            **_empty_result(state),
            "response": _format_web_search_response(payload),
            "thinking_content": _with_thinking(state, f"Busquei informações públicas sobre '{query}'."),
            "tool_calls": [
                _tool_call(
                    name="web_search_tool",
                    tool_input={"query": query},
                    output=payload,
                    request_id=request_id,
                    index=0,
                    display_name="Busca web",
                )
            ],
            "web_result": payload,
            "skip_model_response": True,
        }

    if mode == "web_fetch":
        url = tool_plan.get("web_url") or ""
        payload = fetch_web_content(url)
        return {
            **_empty_result(state),
            "response": _format_web_fetch_response(payload),
            "thinking_content": _with_thinking(state, f"Abri a URL pública {url}."),
            "tool_calls": [
                _tool_call(
                    name="web_fetch_tool",
                    tool_input={"url": url},
                    output=payload,
                    request_id=request_id,
                    index=0,
                    display_name="Leitura web",
                )
            ],
            "web_result": payload,
            "skip_model_response": True,
        }

    if mode == "menu_lookup":
        payload = lookup_company_menu(
            company_id=company_id,
            query=tool_plan.get("menu_query"),
            category=tool_plan.get("menu_category"),
            limit=_safe_limit(tool_plan.get("menu_limit"), 8, maximum=25),
        )
        return {
            **_empty_result(state),
            "response": _format_menu_response(payload),
            "thinking_content": _with_thinking(state, "Consultei o cardápio disponível para responder ao usuário."),
            "tool_calls": [
                _tool_call(
                    name="menu_lookup_tool",
                    tool_input={
                        "company_id": company_id,
                        "query": tool_plan.get("menu_query"),
                        "category": tool_plan.get("menu_category"),
                        "limit": _safe_limit(tool_plan.get("menu_limit"), 8, maximum=25),
                    },
                    output=payload,
                    request_id=request_id,
                    index=0,
                    display_name="Consulta de cardápio",
                )
            ],
            "menu_result": payload,
            "skip_model_response": True,
        }

    if mode == "database_query":
        db = None
        try:
            db_gen = get_db()
            db = next(db_gen)
            payload = _execute_database_query(
                db=db,
                company_id=company_id,
                query_type=tool_plan.get("db_query_type") or "list",
                table=tool_plan.get("db_table") or "products",
                filters=tool_plan.get("db_filters") or {},
                limit=_safe_limit(tool_plan.get("db_limit"), 10, maximum=100),
            )
        finally:
            if db is not None:
                db.close()
        return {
            **_empty_result(state),
            "response": _format_database_response(payload),
            "thinking_content": _with_thinking(state, "Executei uma consulta ao banco restrita à empresa atual."),
            "tool_calls": [
                _tool_call(
                    name="database_query_tool",
                    tool_input={
                        "company_id": company_id,
                        "query_type": tool_plan.get("db_query_type") or "list",
                        "table": tool_plan.get("db_table") or "products",
                        "filters": tool_plan.get("db_filters") or {},
                        "limit": _safe_limit(tool_plan.get("db_limit"), 10, maximum=100),
                    },
                    output=payload,
                    request_id=request_id,
                    index=0,
                    display_name="Consulta ao banco",
                )
            ],
            "db_query_result": payload,
            "skip_model_response": True,
        }

    if mode == "knowledge_store":
        db = None
        try:
            db_gen = get_db()
            db = next(db_gen)
            knowledge_key = tool_plan.get("knowledge_key") or _truncate_text(state.get("current_message") or "", 60)
            knowledge_value = tool_plan.get("knowledge_value") or state.get("current_message") or ""
            knowledge_id = await KnowledgeBase.store(
                db=db,
                company_id=company_id,
                category="general",
                key=knowledge_key,
                value=knowledge_value,
                source_session_id=state.get("session_id"),
            )
        finally:
            if db is not None:
                db.close()
        payload = {"knowledge_id": knowledge_id, "key": knowledge_key, "value": knowledge_value}
        return {
            **_empty_result(state),
            "response": "Informação salva na base de conhecimento.",
            "thinking_content": _with_thinking(state, "Armazenei o conhecimento informado para uso futuro."),
            "tool_calls": [
                _tool_call(
                    name="knowledge_store_tool",
                    tool_input={"key": knowledge_key, "value": knowledge_value},
                    output=payload,
                    request_id=request_id,
                    index=0,
                    display_name="Base de conhecimento",
                )
            ],
            "knowledge_result": payload,
            "skip_model_response": True,
        }

    if mode == "knowledge_search":
        db = None
        try:
            db_gen = get_db()
            db = next(db_gen)
            query = tool_plan.get("knowledge_query") or state.get("current_message") or ""
            items = await KnowledgeBase.search(db=db, company_id=company_id, query=query)
        finally:
            if db is not None:
                db.close()
        payload = {"items": items, "query": query}
        return {
            **_empty_result(state),
            "response": _format_knowledge_response(items),
            "thinking_content": _with_thinking(state, "Busquei conhecimento já armazenado para complementar a resposta."),
            "tool_calls": [
                _tool_call(
                    name="knowledge_search_tool",
                    tool_input={"query": query},
                    output=payload,
                    request_id=request_id,
                    index=0,
                    display_name="Busca em conhecimento",
                )
            ],
            "knowledge_result": payload,
            "skip_model_response": True,
        }

    if mode == "document_create":
        document_payload = await _invoke_document_tool(
            {
                "session_id": state.get("session_id"),
                "company_id": company_id,
                "filename": "documento-super-agent",
                "file_type": tool_plan.get("document_type") or "markdown",
                "content": tool_plan.get("document_content") or state.get("current_message") or "",
                "description": "Documento criado automaticamente pelo Super Agent",
            }
        )
        response = (
            f"Documento criado: {document_payload.get('filename')}"
            if document_payload.get("success")
            else f"Não consegui criar o documento: {document_payload.get('error')}"
        )
        return {
            **_empty_result(state),
            "response": response,
            "thinking_content": _with_thinking(state, "Gerei um documento com base no conteúdo solicitado."),
            "tool_calls": [
                _tool_call(
                    name="create_document_tool",
                    tool_input={
                        "session_id": state.get("session_id"),
                        "company_id": company_id,
                        "file_type": tool_plan.get("document_type") or "markdown",
                    },
                    output=document_payload,
                    request_id=request_id,
                    index=0,
                    display_name="Criação de documento",
                )
            ],
            "document_id": document_payload.get("document_id"),
            "document_type": document_payload.get("file_type"),
            "document_content": tool_plan.get("document_content") or state.get("current_message"),
            "skip_model_response": True,
        }

    return {
        **_empty_result(state),
        "response": None,
        "thinking_content": _with_thinking(state, f"O modo '{mode}' ainda não exige execução automática de ferramenta."),
    }


__all__ = ["execute_tools_for_state", "inference_service"]
