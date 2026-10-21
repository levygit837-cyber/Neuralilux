"""Gerenciamento manual do cardápio: CRUD de Catalog Items."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import MenuItem
from app.schemas.menu import MenuItemCreate, MenuItemUpdate
from app.services.menu.common import (
    _assert_unique_sku,
    _ensure_company_id,
    _get_category_in_catalog,
    _get_item_for_company,
    _normalize_custom_attributes,
    _normalize_required_text,
    _normalize_text,
    _promote_catalog_to_manual,
    _serialize_item,
    get_or_create_active_catalog,
)


def create_menu_item(db: Session, company_id: Optional[str], payload: MenuItemCreate) -> dict[str, Any]:
    resolved_company_id = _ensure_company_id(company_id)
    catalog = get_or_create_active_catalog(db, resolved_company_id)
    _promote_catalog_to_manual(catalog)
    category = _get_category_in_catalog(db, resolved_company_id, catalog.id, payload.category_id)

    # Validate SKU uniqueness if provided
    if payload.sku:
        _assert_unique_sku(db, catalog.id, payload.sku)

    last_sort_order = (
        db.query(MenuItem.sort_order)
        .filter(MenuItem.category_id == category.id)
        .order_by(MenuItem.sort_order.desc())
        .first()
    )
    next_sort_order = (last_sort_order[0] if last_sort_order and last_sort_order[0] is not None else 0) + 1

    item = MenuItem(
        catalog_id=catalog.id,
        category_id=category.id,
        name=_normalize_required_text(payload.name, "Nome do item é obrigatório"),
        description=_normalize_text(payload.description),
        price=payload.price,
        is_available=payload.is_available,
        sort_order=next_sort_order,
        custom_attributes=_normalize_custom_attributes(payload.model_dump().get("custom_attributes")),
        sku=payload.sku,
        stock_quantity=payload.stock_quantity or 0,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


def update_menu_item(
    db: Session,
    company_id: Optional[str],
    item_id: str,
    payload: MenuItemUpdate,
) -> dict[str, Any]:
    resolved_company_id = _ensure_company_id(company_id)
    catalog, item = _get_item_for_company(db, resolved_company_id, item_id)
    _promote_catalog_to_manual(catalog)
    updated_fields = payload.model_dump(exclude_unset=True)

    if "category_id" in updated_fields and payload.category_id is not None:
        category = _get_category_in_catalog(db, resolved_company_id, catalog.id, payload.category_id)
        item.category_id = category.id

    if "name" in updated_fields:
        item.name = _normalize_required_text(payload.name or "", "Nome do item é obrigatório")

    if "description" in updated_fields:
        item.description = _normalize_text(payload.description)

    if "price" in updated_fields:
        item.price = payload.price

    if "is_available" in updated_fields:
        item.is_available = payload.is_available

    if "custom_attributes" in updated_fields:
        item.custom_attributes = _normalize_custom_attributes(payload.model_dump().get("custom_attributes"))

    if "sku" in updated_fields:
        if payload.sku and payload.sku != item.sku:
            _assert_unique_sku(db, catalog.id, payload.sku, ignore_item_id=item.id)
        item.sku = payload.sku

    if "stock_quantity" in updated_fields:
        item.stock_quantity = payload.stock_quantity or 0

    db.commit()
    db.refresh(item)
    return _serialize_item(item)


def delete_menu_item(db: Session, company_id: Optional[str], item_id: str) -> None:
    resolved_company_id = _ensure_company_id(company_id)
    catalog, item = _get_item_for_company(db, resolved_company_id, item_id)
    _promote_catalog_to_manual(catalog)
    db.delete(item)
    db.commit()
