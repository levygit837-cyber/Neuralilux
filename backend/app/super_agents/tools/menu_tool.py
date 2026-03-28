"""Menu lookup tools for the Super Agent."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import structlog
from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Company, MenuCatalog, MenuCategory, MenuItem
from app.services.menu_catalog_service import (
    MACEDOS_COMPANY_DISPLAY_NAME,
    MACEDOS_COMPANY_NAME,
    normalize_text,
    sync_macedos_menu_from_json,
)

logger = structlog.get_logger()


def _is_macedos_company(company: Optional[Company]) -> bool:
    if not company:
        return False
    company_name = normalize_text(company.name)
    return company_name in {
        normalize_text(MACEDOS_COMPANY_NAME),
        normalize_text(MACEDOS_COMPANY_DISPLAY_NAME),
    }


def _ensure_catalog(db: Session, company_id: str) -> Optional[MenuCatalog]:
    catalog = (
        db.query(MenuCatalog)
        .filter(MenuCatalog.company_id == company_id, MenuCatalog.is_active == True)
        .order_by(MenuCatalog.created_at.desc())
        .first()
    )
    if catalog:
        return catalog

    company = db.query(Company).filter(Company.id == company_id).first()
    if _is_macedos_company(company):
        sync_macedos_menu_from_json(db)
        return (
            db.query(MenuCatalog)
            .filter(MenuCatalog.company_id == company_id, MenuCatalog.is_active == True)
            .order_by(MenuCatalog.created_at.desc())
            .first()
        )
    return None


def _serialize_item(item: MenuItem, category_name: str) -> Dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "price": float(item.price) if item.price is not None else None,
        "image_url": item.image_url,
        "category_name": category_name,
        "is_available": bool(item.is_available),
        "sort_order": item.sort_order or 0,
        "custom_attributes": item.custom_attributes or [],
    }


def _item_score(item_payload: Dict[str, Any], query: str) -> tuple[int, int, str]:
    target = normalize_text(query)
    name = normalize_text(item_payload.get("name") or "")
    category = normalize_text(item_payload.get("category_name") or "")
    description = normalize_text(item_payload.get("description") or "")

    if name == target:
        return (0, item_payload.get("sort_order") or 0, name)
    if target and target in name:
        return (1, item_payload.get("sort_order") or 0, name)
    if target and target in category:
        return (2, item_payload.get("sort_order") or 0, name)
    if target and target in description:
        return (3, item_payload.get("sort_order") or 0, name)
    return (4, item_payload.get("sort_order") or 0, name)


def lookup_company_menu(
    company_id: str,
    query: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    db: Optional[Session] = None
    try:
        db_gen = get_db()
        db = next(db_gen)
        catalog = _ensure_catalog(db=db, company_id=company_id)
        if not catalog:
            return {
                "company_id": company_id,
                "catalog": None,
                "categories": [],
                "items": [],
                "count": 0,
            }

        categories = (
            db.query(MenuCategory)
            .filter(MenuCategory.catalog_id == catalog.id)
            .order_by(MenuCategory.sort_order.asc(), MenuCategory.name.asc())
            .all()
        )
        items = (
            db.query(MenuItem, MenuCategory.name.label("category_name"))
            .join(MenuCategory, MenuCategory.id == MenuItem.category_id)
            .filter(MenuItem.catalog_id == catalog.id)
            .order_by(MenuCategory.sort_order.asc(), MenuItem.sort_order.asc(), MenuItem.name.asc())
            .all()
        )
        item_counts_by_category: Dict[str, int] = {}
        for item, category_name in items:
            item_counts_by_category[item.category_id] = item_counts_by_category.get(item.category_id, 0) + 1

        category_filter = normalize_text(category) if category else ""
        query_filter = normalize_text(query) if query else ""

        filtered_items: List[Dict[str, Any]] = []
        for item, category_name in items:
            payload = _serialize_item(item, category_name)
            normalized_category = normalize_text(category_name)
            if category_filter and category_filter not in normalized_category:
                continue
            if query_filter:
                normalized_text = " ".join(
                    [
                        normalize_text(item.name),
                        normalize_text(item.description or ""),
                        normalized_category,
                        normalize_text(
                            " ".join(
                                f"{attribute.get('key', '')} {attribute.get('value', '')}"
                                for attribute in (item.custom_attributes or [])
                                if isinstance(attribute, dict)
                            )
                        ),
                    ]
                )
                if query_filter not in normalized_text:
                    continue
            filtered_items.append(payload)

        if query_filter:
            filtered_items.sort(key=lambda item: _item_score(item, query or ""))

        limited_items = filtered_items[:limit]

        return {
            "company_id": company_id,
            "catalog": {
                "id": catalog.id,
                "name": catalog.name,
                "source_type": catalog.source_type,
            },
            "categories": [
                {
                    "id": category_row.id,
                    "name": category_row.name,
                    "description": category_row.description,
                    "sort_order": category_row.sort_order or 0,
                    "item_count": item_counts_by_category.get(category_row.id, 0),
                }
                for category_row in categories
            ],
            "items": limited_items,
            "count": len(limited_items),
            "total_count": len(filtered_items),
            "query": query,
            "category": category,
        }
    finally:
        if db is not None:
            db.close()


@tool
def menu_lookup_tool(
    company_id: str,
    query: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20,
) -> str:
    """Lookup the active company menu with optional text or category filters."""
    try:
        payload = lookup_company_menu(
            company_id=company_id,
            query=query,
            category=category,
            limit=limit,
        )
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        logger.error("Menu lookup failed", error=str(exc), company_id=company_id)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


__all__ = ["lookup_company_menu", "menu_lookup_tool"]
