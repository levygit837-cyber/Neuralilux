"""Knowledge tools for the Super Agent."""
from __future__ import annotations

import asyncio
import json
from typing import Optional

import structlog
from langchain_core.tools import tool

from app.super_agents.memory.knowledge_base import KnowledgeBase

logger = structlog.get_logger()


def _run_async(coro):
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


@tool
def knowledge_search_tool(
    company_id: str,
    query: str,
    category: Optional[str] = None,
) -> str:
    """
    Search the knowledge base for relevant information.

    Args:
        company_id: Company ID to scope search
        query: Search query text
        category: Optional category filter

    Returns:
        JSON string with search results
    """
    try:
        from app.core.database import get_db

        db_gen = get_db()
        db = next(db_gen)

        try:
            results = _run_async(
                KnowledgeBase.search(
                    db=db,
                    company_id=company_id,
                    query=query,
                    category=category,
                )
            )

            return json.dumps({
                "success": True,
                "results": results,
                "count": len(results),
                "query": query,
                "category": category,
            })

        finally:
            db.close()

    except Exception as e:
        logger.error("Knowledge search failed", error=str(e))
        return json.dumps({"error": str(e)})


@tool
def knowledge_store_tool(
    company_id: str,
    category: str,
    key: str,
    value: str,
    source_session_id: Optional[str] = None,
) -> str:
    """
    Store knowledge in the knowledge base for future reference.

    Args:
        company_id: Company ID
        category: Knowledge category (e.g., "product_knowledge", "customer_insights", "business_rules")
        key: Unique key for this knowledge
        value: The knowledge content
        source_session_id: Optional session that discovered this knowledge

    Returns:
        JSON string with storage result
    """
    try:
        from app.core.database import get_db

        db_gen = get_db()
        db = next(db_gen)

        try:
            knowledge_id = _run_async(
                KnowledgeBase.store(
                    db=db,
                    company_id=company_id,
                    category=category,
                    key=key,
                    value=value,
                    source_session_id=source_session_id,
                )
            )

            if knowledge_id:
                return json.dumps({
                    "success": True,
                    "knowledge_id": knowledge_id,
                    "category": category,
                    "key": key,
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": "Failed to store knowledge",
                })

        finally:
            db.close()

    except Exception as e:
        logger.error("Knowledge store failed", error=str(e))
        return json.dumps({"error": str(e)})