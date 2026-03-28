"""WhatsApp tools and helpers for the Super Agent."""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

import structlog
from langchain_core.tools import tool
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Contact, Instance, User
from app.services.evolution_api import EvolutionAPIService
from app.services.menu_catalog_service import normalize_text

logger = structlog.get_logger()


def _run_async(coro):
    """Helper to run async code in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _serialize_contact(contact: Contact, instance: Instance) -> Dict[str, Any]:
    return {
        "id": contact.id,
        "name": contact.name,
        "push_name": contact.push_name,
        "display_name": contact.name or contact.push_name or contact.phone_number,
        "phone_number": contact.phone_number,
        "remote_jid": contact.remote_jid,
        "instance_id": instance.id,
        "instance_name": instance.evolution_instance_id or instance.name,
        "is_business": bool(contact.is_business),
        "is_blocked": bool(contact.is_blocked),
        "notes": contact.notes,
    }


def _query_company_instances(
    db: Session,
    company_id: str,
    instance_name: Optional[str] = None,
) -> List[Instance]:
    query = (
        db.query(Instance)
        .outerjoin(User, Instance.owner_id == User.id)
        .filter(User.company_id == company_id, Instance.is_active == True)
    )

    if instance_name:
        query = query.filter(
            or_(
                Instance.evolution_instance_id == instance_name,
                Instance.name == instance_name,
            )
        )

    return query.order_by(Instance.created_at.asc()).all()


def _contact_score(contact_payload: Dict[str, Any], search: str) -> tuple[int, str]:
    target = normalize_text(search)
    display_name = normalize_text(contact_payload.get("display_name") or "")
    phone_number = normalize_text(contact_payload.get("phone_number") or "")
    remote_jid = normalize_text(contact_payload.get("remote_jid") or "")

    if not target:
        return (3, display_name)
    if display_name == target or phone_number == target or remote_jid == target:
        return (0, display_name)
    if target in display_name or target in phone_number or target in remote_jid:
        return (1, display_name)
    return (2, display_name)


def _extract_evolution_contacts(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    candidates: Any = (
        payload.get("contacts")
        or payload.get("data")
        or payload.get("records")
        or payload.get("results")
        or []
    )

    if isinstance(candidates, dict):
        candidates = (
            candidates.get("contacts")
            or candidates.get("data")
            or candidates.get("records")
            or candidates.get("results")
            or []
        )

    return [item for item in candidates if isinstance(item, dict)] if isinstance(candidates, list) else []


def _normalize_remote_jid(raw_value: Optional[str]) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""
    if "@" in value:
        return value

    digits = re.sub(r"\D", "", value)
    return f"{digits}@s.whatsapp.net" if digits else value


def _serialize_live_contact(contact_payload: Dict[str, Any], instance: Instance) -> Optional[Dict[str, Any]]:
    raw_number = (
        contact_payload.get("number")
        or contact_payload.get("phone")
        or contact_payload.get("phoneNumber")
        or contact_payload.get("phone_number")
        or ""
    )
    phone_number = re.sub(r"\D", "", str(raw_number))
    remote_jid = _normalize_remote_jid(
        contact_payload.get("remoteJid")
        or contact_payload.get("remote_jid")
        or raw_number
    )

    display_name = (
        contact_payload.get("name")
        or contact_payload.get("pushName")
        or contact_payload.get("push_name")
        or phone_number
        or remote_jid
    )

    if not remote_jid and not display_name:
        return None

    return {
        "id": str(contact_payload.get("id") or remote_jid or phone_number),
        "name": contact_payload.get("name"),
        "push_name": contact_payload.get("pushName") or contact_payload.get("push_name"),
        "display_name": display_name,
        "phone_number": phone_number or None,
        "remote_jid": remote_jid or None,
        "instance_id": instance.id,
        "instance_name": instance.evolution_instance_id or instance.name,
        "is_business": bool(
            contact_payload.get("isBusiness")
            or contact_payload.get("is_business")
            or contact_payload.get("business")
        ),
        "is_blocked": bool(contact_payload.get("isBlocked") or contact_payload.get("is_blocked")),
        "notes": "live_evolution_contact",
    }


def _matches_contact_search(contact_payload: Dict[str, Any], search: Optional[str]) -> bool:
    if not search:
        return True

    target = normalize_text(search)
    searchable = " ".join(
        normalize_text(str(contact_payload.get(field) or ""))
        for field in ["display_name", "phone_number", "remote_jid"]
    )
    return bool(target) and target in searchable


def _query_live_company_contacts(
    db: Session,
    company_id: str,
    search: Optional[str] = None,
    instance_name: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    instances = _query_company_instances(
        db=db,
        company_id=company_id,
        instance_name=instance_name,
    )
    if not instances:
        return []

    evolution = EvolutionAPIService()
    contacts_by_jid: Dict[str, Dict[str, Any]] = {}

    for instance in instances:
        resolved_instance_name = instance.evolution_instance_id or instance.name
        if not resolved_instance_name:
            continue

        async def _fetch():
            return await evolution.fetch_contacts(resolved_instance_name)

        try:
            payload = _run_async(_fetch())
        except Exception as exc:
            logger.warning(
                "Failed to fetch live Evolution contacts",
                company_id=company_id,
                instance_name=resolved_instance_name,
                error=str(exc),
            )
            continue

        for item in _extract_evolution_contacts(payload):
            serialized = _serialize_live_contact(item, instance)
            if not serialized or not _matches_contact_search(serialized, search):
                continue

            dedupe_key = serialized.get("remote_jid") or serialized.get("phone_number") or serialized.get("id")
            if dedupe_key and dedupe_key not in contacts_by_jid:
                contacts_by_jid[dedupe_key] = serialized

    contacts = list(contacts_by_jid.values())
    if search:
        contacts.sort(key=lambda item: _contact_score(item, search))
    else:
        contacts.sort(key=lambda item: normalize_text(item.get("display_name") or ""))
    return contacts[:limit]


def _query_company_contacts(
    db: Session,
    company_id: str,
    search: Optional[str] = None,
    instance_name: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    query = (
        db.query(Contact, Instance)
        .join(Instance, Contact.instance_id == Instance.id)
        .outerjoin(User, Instance.owner_id == User.id)
        .filter(User.company_id == company_id, Instance.is_active == True)
    )

    if instance_name:
        query = query.filter(
            or_(
                Instance.evolution_instance_id == instance_name,
                Instance.name == instance_name,
            )
        )

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Contact.name.ilike(pattern),
                Contact.push_name.ilike(pattern),
                Contact.phone_number.ilike(pattern),
                Contact.remote_jid.ilike(pattern),
            )
        )

    rows = query.limit(max(limit * 2, limit)).all()
    contacts = [_serialize_contact(contact, instance) for contact, instance in rows]
    if search:
        contacts.sort(key=lambda item: _contact_score(item, search))
    else:
        contacts.sort(key=lambda item: normalize_text(item.get("display_name") or ""))
    return contacts[:limit]


def _merge_contact_sources(
    *,
    live_contacts: List[Dict[str, Any]],
    persisted_contacts: List[Dict[str, Any]],
    search: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}

    def _dedupe_key(contact_payload: Dict[str, Any]) -> Optional[str]:
        return (
            contact_payload.get("remote_jid")
            or contact_payload.get("phone_number")
            or contact_payload.get("id")
        )

    for contact in live_contacts:
        key = _dedupe_key(contact)
        if key:
            merged[key] = dict(contact)

    for contact in persisted_contacts:
        key = _dedupe_key(contact)
        if not key:
            continue

        existing = merged.get(key)
        if not existing:
            merged[key] = dict(contact)
            continue

        for field, value in contact.items():
            if existing.get(field) in (None, "", False) and value not in (None, ""):
                existing[field] = value

    contacts = list(merged.values())
    if search:
        contacts.sort(key=lambda item: _contact_score(item, search))
    else:
        contacts.sort(key=lambda item: normalize_text(item.get("display_name") or ""))
    return contacts[:limit]


def list_company_contacts(
    company_id: str,
    search: Optional[str] = None,
    instance_name: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    db: Optional[Session] = None
    try:
        db_gen = get_db()
        db = next(db_gen)
        live_contacts = _query_live_company_contacts(
            db=db,
            company_id=company_id,
            search=search,
            instance_name=instance_name,
            limit=limit,
        )
        persisted_contacts = _query_company_contacts(
            db=db,
            company_id=company_id,
            search=search,
            instance_name=instance_name,
            limit=limit,
        )

        if live_contacts or persisted_contacts:
            return _merge_contact_sources(
                live_contacts=live_contacts,
                persisted_contacts=persisted_contacts,
                search=search,
                limit=limit,
            )

        return []
    finally:
        if db is not None:
            db.close()


def resolve_company_contacts(
    company_id: str,
    query: str,
    instance_name: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    return list_company_contacts(
        company_id=company_id,
        search=query,
        instance_name=instance_name,
        limit=limit,
    )


def _extract_message_text(message_payload: Dict[str, Any]) -> str:
    message = message_payload.get("message", {})
    return (
        message.get("conversation", "")
        or message.get("extendedTextMessage", {}).get("text", "")
        or message.get("imageMessage", {}).get("caption", "")
        or message.get("videoMessage", {}).get("caption", "")
        or ""
    )


def read_messages_for_contact(
    instance_name: str,
    remote_jid: str,
    limit: int = 20,
) -> Dict[str, Any]:
    evolution = EvolutionAPIService()

    async def _read():
        return await evolution.fetch_messages(
            instance_name=instance_name,
            remote_jid=remote_jid,
            offset=min(limit, 100),
        )

    result = _run_async(_read())
    raw_messages = []
    if isinstance(result, list):
        raw_messages = result
    elif isinstance(result, dict):
        raw_messages = (
            result.get("messages")
            or result.get("data")
            or result.get("records")
            or []
        )

    messages = []
    for msg in raw_messages[:limit]:
        if not isinstance(msg, dict):
            continue
        messages.append(
            {
                "id": msg.get("key", {}).get("id", "") or msg.get("id", ""),
                "from_me": msg.get("key", {}).get("fromMe", False),
                "timestamp": msg.get("messageTimestamp", "") or msg.get("timestamp", ""),
                "content": _extract_message_text(msg),
                "push_name": msg.get("pushName", ""),
            }
        )

    return {
        "messages": messages,
        "count": len(messages),
        "instance_name": instance_name,
        "remote_jid": remote_jid,
    }


def send_message_via_whatsapp(
    instance_name: str,
    remote_jid: str,
    message: str,
) -> Dict[str, Any]:
    evolution = EvolutionAPIService()

    async def _send():
        return await evolution.send_text_message(
            instance_name=instance_name,
            remote_jid=remote_jid,
            text=message,
        )

    result = _run_async(_send())
    return {
        "success": True,
        "message": "Message sent successfully",
        "instance_name": instance_name,
        "remote_jid": remote_jid,
        "result": result,
    }


def send_bulk_messages_via_whatsapp(
    recipients: List[Dict[str, Any]],
    message: str,
) -> Dict[str, Any]:
    results = []
    success_count = 0
    fail_count = 0

    for recipient in recipients:
        instance_name = recipient.get("instance_name")
        remote_jid = recipient.get("remote_jid")
        try:
            send_message_via_whatsapp(
                instance_name=instance_name,
                remote_jid=remote_jid,
                message=message,
            )
            results.append(
                {
                    "jid": remote_jid,
                    "display_name": recipient.get("display_name"),
                    "instance_name": instance_name,
                    "success": True,
                }
            )
            success_count += 1
        except Exception as exc:
            results.append(
                {
                    "jid": remote_jid,
                    "display_name": recipient.get("display_name"),
                    "instance_name": instance_name,
                    "success": False,
                    "error": str(exc),
                }
            )
            fail_count += 1

    return {
        "success": fail_count == 0,
        "total": len(recipients),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results,
    }


@tool
def whatsapp_list_contacts_tool(
    company_id: str,
    search: Optional[str] = None,
    instance_name: Optional[str] = None,
    limit: int = 20,
) -> str:
    """List contacts available to a company, optionally filtering by search text."""
    try:
        contacts = list_company_contacts(
            company_id=company_id,
            search=search,
            instance_name=instance_name,
            limit=limit,
        )
        return json.dumps(
            {
                "contacts": contacts,
                "count": len(contacts),
                "company_id": company_id,
                "instance_name": instance_name,
                "search": search,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        logger.error("Failed to list WhatsApp contacts", error=str(exc), company_id=company_id)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def whatsapp_resolve_contacts_tool(
    company_id: str,
    query: str,
    instance_name: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Resolve contacts by name, phone or JID for a company."""
    try:
        contacts = resolve_company_contacts(
            company_id=company_id,
            query=query,
            instance_name=instance_name,
            limit=limit,
        )
        return json.dumps(
            {
                "contacts": contacts,
                "count": len(contacts),
                "company_id": company_id,
                "query": query,
                "instance_name": instance_name,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        logger.error("Failed to resolve WhatsApp contacts", error=str(exc), company_id=company_id)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def whatsapp_read_messages_tool(
    instance_name: str,
    remote_jid: str,
    limit: int = 20,
) -> str:
    """Read messages from a WhatsApp contact conversation."""
    try:
        payload = read_messages_for_contact(
            instance_name=instance_name,
            remote_jid=remote_jid,
            limit=limit,
        )
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        logger.error("Failed to read WhatsApp messages", error=str(exc), instance_name=instance_name)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def whatsapp_send_message_tool(
    instance_name: str,
    remote_jid: str,
    message: str,
) -> str:
    """Send a WhatsApp text message to a single contact."""
    try:
        payload = send_message_via_whatsapp(
            instance_name=instance_name,
            remote_jid=remote_jid,
            message=message,
        )
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        logger.error("Failed to send WhatsApp message", error=str(exc), instance_name=instance_name)
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


@tool
def whatsapp_send_bulk_tool(
    instance_name: str,
    remote_jids: List[str],
    message: str,
) -> str:
    """Send the same WhatsApp text message to multiple recipients in one instance."""
    try:
        recipients = [
            {
                "instance_name": instance_name,
                "remote_jid": remote_jid,
                "display_name": remote_jid,
            }
            for remote_jid in remote_jids
        ]
        payload = send_bulk_messages_via_whatsapp(recipients=recipients, message=message)
        payload["instance_name"] = instance_name
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        logger.error("Failed to send bulk WhatsApp messages", error=str(exc), instance_name=instance_name)
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


__all__ = [
    "list_company_contacts",
    "read_messages_for_contact",
    "resolve_company_contacts",
    "send_bulk_messages_via_whatsapp",
    "send_message_via_whatsapp",
    "whatsapp_list_contacts_tool",
    "whatsapp_read_messages_tool",
    "whatsapp_resolve_contacts_tool",
    "whatsapp_send_bulk_tool",
    "whatsapp_send_message_tool",
]
