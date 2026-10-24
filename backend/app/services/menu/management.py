"""Gerenciamento manual do cardápio: snapshot da Company e CRUD de Categories."""
from __future__ import annotations

from collections import Counter
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import MenuCategory, MenuItem
from app.schemas.catalog import MenuCategoryCreate, MenuCategoryUpdate
from app.services.menu.common import (
    _assert_unique_category_name,
    _ensure_company_id,
    _get_category_for_company,
    _normalize_required_text,
    _normalize_text,
    _promote_catalog_to_manual,
    _serialize_category,
    _serialize_item,
    get_or_create_active_catalog,
)


def get_menu_management_snapshot(db: Session, company_id: Optional[str]) -> dict[str, Any]:
    catalog = get_or_create_active_catalog(db, company_id)

    categories = (
        db.query(MenuCategory)
        .filter(MenuCategory.catalog_id == catalog.id)
        .order_by(MenuCategory.sort_order.asc(), MenuCategory.name.asc())
        .all()
    )
    items = (
        db.query(MenuItem)
        .filter(MenuItem.catalog_id == catalog.id)
        .order_by(MenuItem.sort_order.asc(), MenuItem.name.asc())
        .all()
    )

    counts = Counter(item.category_id for item in items)

    return {
        "catalog": {
            "id": catalog.id,
            "name": catalog.name,
            "source_type": catalog.source_type,
        },
        "categories": [_serialize_category(category, counts.get(category.id, 0)) for category in categories],
        "items": [_serialize_item(item) for item in items],
    }


def create_menu_category(db: Session, company_id: Optional[str], payload: MenuCategoryCreate) -> dict[str, Any]:
    resolved_company_id = _ensure_company_id(company_id)
    catalog = get_or_create_active_catalog(db, resolved_company_id)
    _promote_catalog_to_manual(catalog)

    category_name = _normalize_required_text(payload.name, "Nome da categoria é obrigatório")
    _assert_unique_category_name(db, catalog.id, category_name)

    last_sort_order = (
        db.query(MenuCategory.sort_order)
        .filter(MenuCategory.catalog_id == catalog.id)
        .order_by(MenuCategory.sort_order.desc())
        .first()
    )
    next_sort_order = (last_sort_order[0] if last_sort_order and last_sort_order[0] is not None else 0) + 1

    category = MenuCategory(
        catalog_id=catalog.id,
        name=category_name,
        description=_normalize_text(payload.description),
        sort_order=next_sort_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    db.refresh(catalog)
    return _serialize_category(category, 0)


def update_menu_category(
    db: Session,
    company_id: Optional[str],
    category_id: str,
    payload: MenuCategoryUpdate,
) -> dict[str, Any]:
    resolved_company_id = _ensure_company_id(company_id)
    catalog, category = _get_category_for_company(db, resolved_company_id, category_id)
    _promote_catalog_to_manual(catalog)

    updated_fields = payload.model_dump(exclude_unset=True)

    if "name" in updated_fields:
        category_name = _normalize_required_text(payload.name or "", "Nome da categoria é obrigatório")
        _assert_unique_category_name(db, catalog.id, category_name, ignore_category_id=category.id)
        category.name = category_name

    if "description" in updated_fields:
        category.description = _normalize_text(payload.description)

    db.commit()
    db.refresh(category)
    return _serialize_category(category, db.query(MenuItem).filter(MenuItem.category_id == category.id).count())


def delete_menu_category(db: Session, company_id: Optional[str], category_id: str) -> None:
    resolved_company_id = _ensure_company_id(company_id)
    catalog, category = _get_category_for_company(db, resolved_company_id, category_id)
    _promote_catalog_to_manual(catalog)

    # Check for items with stock
    items_with_stock = (
        db.query(MenuItem)
        .filter(MenuItem.category_id == category.id, MenuItem.stock_quantity > 0)
        .all()
    )
    if items_with_stock:
        item_names = [item.name for item in items_with_stock]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível excluir categoria com itens em estoque: {', '.join(item_names)}",
        )

    db.query(MenuItem).filter(MenuItem.category_id == category.id).delete(synchronize_session=False)
    db.delete(category)
    db.commit()
