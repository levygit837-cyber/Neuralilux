"""Dispatcher that maps native tool_call names to Python functions."""
from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

from app.core.database import get_db
from app.super_agents.memory.knowledge_base import KnowledgeBase
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
    async_read_messages_for_contact,
    async_send_message_via_whatsapp,
    async_send_bulk_messages,
)
from app.super_agents.tools.schemas import (
    ListContactsToolInput,
    ReadMessagesToolInput,
    SendMessageToolInput,
    ToolExecutionResult,
    get_tool_timeout,
)
from app.super_agents.tools.executor import execute_with_timeout

logger = structlog.get_logger()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: Any, default: int, maximum: int = 100) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))


def _parse_tool_output(raw_output: Any) -> Dict[str, Any]:
    if isinstance(raw_output, dict):
        return raw_output
    if isinstance(raw_output, str):
        try:
            parsed = json.loads(raw_output)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"value": raw_output}
    if isinstance(raw_output, list):
        return {"items": raw_output, "count": len(raw_output)}
    return {"value": raw_output}


async def dispatch_tool_call(
    name: str,
    arguments: Dict[str, Any],
    company_id: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a tool by name with the given arguments.

    Returns a dict with at least ``success`` and ``result`` keys.
    The ``result`` value is always a JSON-serializable dict.
    """
    logger.info("Dispatching tool call", tool=name, args_keys=list(arguments.keys()))

    try:
        result = await _dispatch(name, arguments, company_id, session_id)
        return {"success": True, "result": _parse_tool_output(result)}
    except Exception as exc:
        logger.error("Tool dispatch error", tool=name, error=str(exc))
        return {"success": False, "result": {"error": str(exc)}}


async def _dispatch(
    name: str,
    args: Dict[str, Any],
    company_id: str,
    session_id: Optional[str],
) -> Any:

    if name == "whatsapp_list_contacts":
        # Validate input
        try:
            validated = ListContactsToolInput(company_id=company_id, **args)
        except Exception as exc:
            logger.warning(
                "whatsapp_list_contacts validation failed",
                error=str(exc),
                company_id=company_id,
            )
            return {"error": f"Invalid input: {str(exc)}", "contacts": [], "count": 0}
        
        # Execute with timeout
        result = await execute_with_timeout(
            _list_contacts_with_fallback(
                company_id=validated.company_id,
                search=validated.search,
                instance_name=validated.instance_name,
                limit=validated.limit,
            ),
            tool_name=name,
            timeout_seconds=get_tool_timeout(name),
            company_id=company_id,
        )
        
        if result.success:
            return result.result
        else:
            # Return empty list on failure
            return {
                "error": result.error,
                "contacts": [],
                "count": 0,
                "_execution_status": result.status,
                "_execution_time_ms": result.execution_time_ms,
            }

    if name == "whatsapp_resolve_contacts":
        # Validate input
        try:
            validated = ListContactsToolInput(
                company_id=company_id,
                search=args.get("query"),
                limit=_safe_int(args.get("limit"), 10, 50),
            )
        except Exception as exc:
            logger.warning(
                "whatsapp_resolve_contacts validation failed",
                error=str(exc),
                company_id=company_id,
            )
            return {"error": f"Invalid input: {str(exc)}", "contacts": [], "count": 0}
        
        # Execute with timeout
        result = await execute_with_timeout(
            _list_contacts_with_fallback(
                company_id=validated.company_id,
                search=validated.search,
                instance_name=validated.instance_name,
                limit=validated.limit,
            ),
            tool_name=name,
            timeout_seconds=get_tool_timeout(name),
            company_id=company_id,
        )
        
        if result.success:
            return result.result
        else:
            return {
                "error": result.error,
                "contacts": [],
                "count": 0,
                "_execution_status": result.status,
                "_execution_time_ms": result.execution_time_ms,
            }

    if name == "whatsapp_read_messages":
        # Validate input
        try:
            validated = ReadMessagesToolInput(
                instance_name=args["instance_name"],
                remote_jid=args["remote_jid"],
                limit=_safe_int(args.get("limit"), 20, 50),
            )
        except Exception as exc:
            logger.warning(
                "whatsapp_read_messages validation failed",
                error=str(exc),
                company_id=company_id,
            )
            return {"error": f"Invalid input: {str(exc)}", "messages": [], "count": 0}
        
        # Execute with timeout
        result = await execute_with_timeout(
            async_read_messages_for_contact(
                instance_name=validated.instance_name,
                remote_jid=validated.remote_jid,
                limit=validated.limit,
            ),
            tool_name=name,
            timeout_seconds=get_tool_timeout(name),
            company_id=company_id,
        )
        
        if result.success:
            return result.result
        else:
            return {
                "error": result.error,
                "messages": [],
                "count": 0,
                "_execution_status": result.status,
                "_execution_time_ms": result.execution_time_ms,
            }

    if name == "whatsapp_send_message":
        # Validate input
        try:
            validated = SendMessageToolInput(
                instance_name=args["instance_name"],
                remote_jid=args["remote_jid"],
                message=args["message"],
            )
        except Exception as exc:
            logger.warning(
                "whatsapp_send_message validation failed",
                error=str(exc),
                company_id=company_id,
            )
            return {"success": False, "error": f"Invalid input: {str(exc)}"}
        
        # Execute with timeout
        result = await execute_with_timeout(
            async_send_message_via_whatsapp(
                instance_name=validated.instance_name,
                remote_jid=validated.remote_jid,
                message=validated.message,
            ),
            tool_name=name,
            timeout_seconds=get_tool_timeout(name),
            company_id=company_id,
        )
        
        if result.success:
            return result.result
        else:
            return {
                "success": False,
                "error": result.error,
                "_execution_status": result.status,
                "_execution_time_ms": result.execution_time_ms,
            }

    if name == "whatsapp_send_bulk":
        # Validate recipients and message
        recipients = args.get("recipients", [])
        message = args.get("message", "")
        
        if not recipients:
            return {"success": False, "error": "No recipients provided"}
        
        if not message or not message.strip():
            return {"success": False, "error": "Message cannot be empty"}
        
        # Validate each recipient has required fields
        for i, recipient in enumerate(recipients):
            if not recipient.get("instance_name"):
                return {"success": False, "error": f"Recipient {i} missing instance_name"}
            if not recipient.get("remote_jid"):
                return {"success": False, "error": f"Recipient {i} missing remote_jid"}
        
        # Execute with timeout (longer for bulk - 30s)
        result = await execute_with_timeout(
            async_send_bulk_messages(
                recipients=recipients,
                message=message,
            ),
            tool_name=name,
            timeout_seconds=get_tool_timeout(name),
            company_id=company_id,
        )
        
        if result.success:
            return result.result
        else:
            return {
                "success": False,
                "error": result.error,
                "_execution_status": result.status,
                "_execution_time_ms": result.execution_time_ms,
            }

    if name == "database_query":
        db = None
        try:
            db_gen = get_db()
            db = next(db_gen)
            return _execute_database_query(
                db=db,
                company_id=company_id,
                query_type=args.get("query_type", "list"),
                table=args.get("table", "products"),
                filters=args.get("filters") or {},
                limit=_safe_int(args.get("limit"), 10, 100),
            )
        finally:
            if db is not None:
                db.close()

    if name == "menu_lookup":
        return lookup_company_menu(
            company_id=company_id,
            query=args.get("query"),
            category=args.get("category"),
            limit=_safe_int(args.get("limit"), 8, 25),
        )

    if name == "web_search":
        return search_web(
            query=args.get("query", ""),
            max_results=_safe_int(args.get("max_results"), 5, 10),
        )

    if name == "web_fetch":
        return fetch_web_content(url=args.get("url", ""))

    if name == "knowledge_store":
        db = None
        try:
            db_gen = get_db()
            db = next(db_gen)
            knowledge_id = await KnowledgeBase.store(
                db=db,
                company_id=company_id,
                category="general",
                key=args.get("key", ""),
                value=args.get("value", ""),
                source_session_id=session_id,
            )
            return {"knowledge_id": knowledge_id, "key": args.get("key"), "stored": True}
        finally:
            if db is not None:
                db.close()

    if name == "knowledge_search":
        db = None
        try:
            db_gen = get_db()
            db = next(db_gen)
            items = await KnowledgeBase.search(
                db=db,
                company_id=company_id,
                query=args.get("query", ""),
            )
            return {"items": items, "count": len(items)}
        finally:
            if db is not None:
                db.close()

    if name == "document_create":
        payload = {
            "session_id": session_id or "",
            "company_id": company_id,
            "filename": args.get("filename", "documento-super-agent"),
            "file_type": args.get("file_type", "markdown"),
            "content": args.get("content", ""),
            "description": args.get("description", "Documento criado pelo Super Agent"),
        }
        if hasattr(create_document_tool, "ainvoke"):
            raw = await create_document_tool.ainvoke(payload)
        elif hasattr(create_document_tool, "invoke"):
            raw = create_document_tool.invoke(payload)
        else:
            raw = create_document_tool(**payload)

        if inspect.isawaitable(raw):
            raw = await raw

        return _parse_tool_output(raw)

    raise ValueError(f"Unknown tool: {name}")


async def _list_contacts_with_fallback(
    company_id: str,
    search: Optional[str] = None,
    instance_name: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """Fetch contacts with fallback to database-only if Evolution API times out.
    
    This function first tries to fetch from Evolution API (live contacts) but if
    that times out, it falls back to database-only query to avoid blocking the user.
    """
    from app.core.database import get_db
    from app.super_agents.tools.whatsapp_tool import _query_company_contacts
    
    db = None
    try:
        db_gen = get_db()
        db = next(db_gen)
        
        # Try to get live contacts with a shorter timeout (5s)
        evolution = None
        live_contacts = []
        
        try:
            from app.super_agents.tools.whatsapp_tool import _query_company_instances, _query_live_company_contacts
            
            instances = _query_company_instances(
                db=db,
                company_id=company_id,
                instance_name=instance_name,
            )
            
            if instances:
                # Try live query with very short timeout to avoid blocking
                evolution = None  # Will be initialized inside _query_live_company_contacts
                
                # Use direct query with timeout via asyncio
                import asyncio
                from app.services.evolution_api import EvolutionAPIService
                
                evolution = EvolutionAPIService()
                contacts_by_jid = {}
                
                for instance in instances[:1]:  # Only try first instance to avoid multiple slow calls
                    resolved_name = instance.evolution_instance_id or instance.name
                    if not resolved_name:
                        continue
                    
                    try:
                        # Quick 5-second timeout for live contacts
                        result = await asyncio.wait_for(
                            evolution.fetch_contacts(resolved_name),
                            timeout=5.0
                        )
                        
                        # Parse result
                        from app.super_agents.tools.whatsapp_tool import _extract_evolution_contacts, _serialize_live_contact
                        
                        for item in _extract_evolution_contacts(result):
                            serialized = _serialize_live_contact(item, instance)
                            if serialized:
                                from app.super_agents.tools.whatsapp_tool import _matches_contact_search
                                if not search or _matches_contact_search(serialized, search):
                                    key = serialized.get("remote_jid") or serialized.get("phone_number") or serialized.get("id")
                                    if key and key not in contacts_by_jid:
                                        contacts_by_jid[key] = serialized
                        
                        live_contacts = list(contacts_by_jid.values())
                        
                        logger.info(
                            "Live contacts fetched successfully",
                            company_id=company_id,
                            instance_name=resolved_name,
                            count=len(live_contacts),
                        )
                        
                    except asyncio.TimeoutError:
                        logger.warning(
                            "Live contacts fetch timed out, using DB fallback",
                            company_id=company_id,
                            instance_name=resolved_name,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Live contacts fetch failed, using DB fallback",
                            company_id=company_id,
                            error=str(exc),
                        )
        
        except Exception as exc:
            logger.warning(
                "Could not fetch live contacts, using DB fallback",
                company_id=company_id,
                error=str(exc),
            )
        
        # Always get persisted contacts from database
        persisted_contacts = _query_company_contacts(
            db=db,
            company_id=company_id,
            search=search,
            instance_name=instance_name,
            limit=limit,
        )
        
        # Merge sources
        if live_contacts:
            from app.super_agents.tools.whatsapp_tool import _merge_contact_sources
            
            return {
                "contacts": _merge_contact_sources(
                    live_contacts=live_contacts,
                    persisted_contacts=persisted_contacts,
                    search=search,
                    limit=limit,
                ),
                "count": len(live_contacts) + len(persisted_contacts),
                "_used_live": True,
                "_used_fallback": False,
            }
        
        # Return only persisted contacts
        return {
            "contacts": persisted_contacts,
            "count": len(persisted_contacts),
            "_used_live": False,
            "_used_fallback": True,
        }
        
    finally:
        if db is not None:
            db.close()
