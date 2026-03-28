"""Database tools for the Super Agent with strict company scoping."""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple

import structlog
from langchain_core.tools import tool
from sqlalchemy import func, desc, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import (
    Company,
    Contact,
    Conversation,
    Instance,
    MenuCatalog,
    MenuCategory,
    MenuItem,
    Message,
    Product,
    User,
)

logger = structlog.get_logger()


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _model_columns(model: Any) -> List[str]:
    return [column.name for column in model.__table__.columns]


def _serialize_model(model: Any, item: Any, columns: Optional[List[str]] = None) -> Dict[str, Any]:
    selected_columns = columns or _model_columns(model)
    payload: Dict[str, Any] = {}
    for column in selected_columns:
        if hasattr(item, column):
            payload[column] = _serialize_value(getattr(item, column))
    return payload


def _build_scoped_query(db: Session, company_id: str, table: str) -> Tuple[Any, Any]:
    table = table.lower().strip()

    if table == "company":
        return db.query(Company).filter(Company.id == company_id), Company

    if table == "products":
        return db.query(Product).filter(Product.company_id == company_id), Product

    if table == "instances":
        query = (
            db.query(Instance)
            .outerjoin(User, Instance.owner_id == User.id)
            .filter(User.company_id == company_id, Instance.is_active == True)
        )
        return query, Instance

    if table == "contacts":
        query = (
            db.query(Contact)
            .join(Instance, Contact.instance_id == Instance.id)
            .outerjoin(User, Instance.owner_id == User.id)
            .filter(User.company_id == company_id, Instance.is_active == True)
        )
        return query, Contact

    if table == "conversations":
        query = (
            db.query(Conversation)
            .join(Instance, Conversation.instance_id == Instance.id)
            .outerjoin(User, Instance.owner_id == User.id)
            .filter(User.company_id == company_id, Instance.is_active == True)
        )
        return query, Conversation

    if table == "messages":
        query = (
            db.query(Message)
            .join(Instance, Message.instance_id == Instance.id)
            .outerjoin(User, Instance.owner_id == User.id)
            .filter(User.company_id == company_id, Instance.is_active == True)
        )
        return query, Message

    if table == "menu_catalogs":
        query = db.query(MenuCatalog).filter(MenuCatalog.company_id == company_id)
        return query, MenuCatalog

    if table == "menu_categories":
        query = (
            db.query(MenuCategory)
            .join(MenuCatalog, MenuCategory.catalog_id == MenuCatalog.id)
            .filter(MenuCatalog.company_id == company_id)
        )
        return query, MenuCategory

    if table == "menu_items":
        query = (
            db.query(MenuItem)
            .join(MenuCatalog, MenuItem.catalog_id == MenuCatalog.id)
            .filter(MenuCatalog.company_id == company_id)
        )
        return query, MenuItem

    raise ValueError(
        "Invalid table: "
        f"{table}. Valid tables: products, contacts, conversations, messages, company, "
        "instances, menu_catalogs, menu_categories, menu_items"
    )


def _apply_filters(query: Any, model: Any, filters: Dict[str, Any]) -> Any:
    for key, value in filters.items():
        if key in {"q", "group_by"}:
            continue
        if not hasattr(model, key):
            continue
        column = getattr(model, key)
        if isinstance(value, str) and "%" in value:
            query = query.filter(column.ilike(value))
        elif isinstance(value, list):
            query = query.filter(column.in_(value))
        else:
            query = query.filter(column == value)
    return query


def _text_search_columns(model: Any) -> List[str]:
    columns: List[str] = []
    for column in model.__table__.columns:
        try:
            if column.type.python_type == str and column.name != "id":
                columns.append(column.name)
        except NotImplementedError:
            continue
    return columns


def _execute_database_query(
    db: Session,
    company_id: str,
    query_type: str,
    table: str,
    filters: Optional[Dict[str, Any]] = None,
    columns: Optional[List[str]] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    limit = min(max(limit, 1), 100)
    filters = filters or {}
    query_type = query_type.lower().strip()
    query, model = _build_scoped_query(db=db, company_id=company_id, table=table)
    query = _apply_filters(query, model, filters)

    if query_type == "count":
        return {"table": table, "count": query.count()}

    if query_type == "aggregate":
        group_by = filters.get("group_by")
        if not group_by or not hasattr(model, group_by):
            return {"error": "aggregate requires a valid 'group_by' filter"}
        group_column = getattr(model, group_by)
        rows = (
            query.group_by(group_column)
            .with_entities(group_column, func.count(getattr(model, "id")).label("count"))
            .limit(limit)
            .all()
        )
        return {
            "table": table,
            "aggregates": [
                {group_by: _serialize_value(row[0]), "count": row[1]}
                for row in rows
            ],
        }

    if query_type == "search":
        search_term = (filters.get("q") or "").strip()
        if not search_term:
            return {"error": "search requires the 'q' filter"}
        search_pattern = f"%{search_term}%"
        text_columns = _text_search_columns(model)
        conditions = [
            getattr(model, column).ilike(search_pattern)
            for column in text_columns
            if hasattr(model, column)
        ]
        if conditions:
            query = query.filter(or_(*conditions))
        total_count = query.count()
        rows = query.order_by(desc(getattr(model, "created_at", getattr(model, "id")))).limit(limit).all()
        return {
            "table": table,
            "count": len(rows),
            "total_count": total_count,
            "query": search_term,
            "items": [_serialize_model(model, row, columns) for row in rows],
        }

    if query_type == "list":
        total_count = query.count()
        rows = query.order_by(desc(getattr(model, "created_at", getattr(model, "id")))).limit(limit).all()
        return {
            "table": table,
            "count": len(rows),
            "total_count": total_count,
            "items": [_serialize_model(model, row, columns) for row in rows],
        }

    return {
        "error": f"Invalid query_type: {query_type}. Valid values: list, count, aggregate, search"
    }


@tool
def database_query_tool(
    company_id: str,
    query_type: str,
    table: str,
    filters: Optional[Dict[str, Any]] = None,
    columns: Optional[List[str]] = None,
    limit: int = 20,
) -> str:
    """
    Execute read-only database queries scoped to a company.

    Supported tables: products, contacts, conversations, messages,
    company, instances, menu_catalogs, menu_categories, menu_items.
    Supported query types: list, count, aggregate, search.
    """
    db: Optional[Session] = None
    try:
        db_gen = get_db()
        db = next(db_gen)
        payload = _execute_database_query(
            db=db,
            company_id=company_id,
            query_type=query_type,
            table=table,
            filters=filters,
            columns=columns,
            limit=limit,
        )
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        logger.error("Database query failed", error=str(exc), table=table, query_type=query_type)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


__all__ = ["database_query_tool", "_execute_database_query"]
