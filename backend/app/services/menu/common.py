"""Helpers compartilhados do gerenciamento manual do cardápio (Catalog, Categories e Items da Company)."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import MenuCatalog, MenuCategory, MenuItem


DEFAULT_MANUAL_CATALOG_NAME = "Cardápio"


def _ensure_company_id(company_id: Optional[str]) -> str:
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário sem empresa vinculada",
        )
    return company_id


def _normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_required_text(value: str, detail: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    return normalized


def _normalize_custom_attributes(custom_attributes: Optional[list[dict[str, Any]]]) -> list[dict[str, str]]:
    normalized_attributes: list[dict[str, str]] = []

    for attribute in custom_attributes or []:
        key = str(attribute.get("key") or "").strip()
        value = str(attribute.get("value") or "").strip()
        if not key or not value:
            continue
        normalized_attributes.append({"key": key, "value": value})

    return normalized_attributes


def _promote_catalog_to_manual(catalog: MenuCatalog) -> None:
    if catalog.source_type != "manual":
        catalog.source_type = "manual"
    if catalog.source_file is not None:
        catalog.source_file = None


def get_or_create_active_catalog(db: Session, company_id: Optional[str]) -> MenuCatalog:
    resolved_company_id = _ensure_company_id(company_id)

    catalog = (
        db.query(MenuCatalog)
        .filter(MenuCatalog.company_id == resolved_company_id, MenuCatalog.is_active == True)
        .order_by(MenuCatalog.created_at.desc())
        .first()
    )
    if catalog:
        return catalog

    catalog = MenuCatalog(
        company_id=resolved_company_id,
        name=DEFAULT_MANUAL_CATALOG_NAME,
        source_type="manual",
        is_active=True,
    )
    db.add(catalog)
    db.commit()
    db.refresh(catalog)
    return catalog


def _get_category_for_company(db: Session, company_id: str, category_id: str) -> tuple[MenuCatalog, MenuCategory]:
    category = (
        db.query(MenuCategory)
        .join(MenuCatalog, MenuCategory.catalog_id == MenuCatalog.id)
        .filter(
            MenuCategory.id == category_id,
            MenuCatalog.company_id == company_id,
            MenuCatalog.is_active == True,
        )
        .first()
    )
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")

    catalog = (
        db.query(MenuCatalog)
        .filter(MenuCatalog.id == category.catalog_id)
        .first()
    )
    if not catalog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catálogo não encontrado")
    return catalog, category


def _get_item_for_company(db: Session, company_id: str, item_id: str) -> tuple[MenuCatalog, MenuItem]:
    item = (
        db.query(MenuItem)
        .join(MenuCatalog, MenuItem.catalog_id == MenuCatalog.id)
        .filter(
            MenuItem.id == item_id,
            MenuCatalog.company_id == company_id,
            MenuCatalog.is_active == True,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado")

    catalog = (
        db.query(MenuCatalog)
        .filter(MenuCatalog.id == item.catalog_id)
        .first()
    )
    if not catalog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catálogo não encontrado")
    return catalog, item


def _get_category_in_catalog(db: Session, company_id: str, catalog_id: str, category_id: str) -> MenuCategory:
    category = (
        db.query(MenuCategory)
        .join(MenuCatalog, MenuCategory.catalog_id == MenuCatalog.id)
        .filter(
            MenuCategory.id == category_id,
            MenuCategory.catalog_id == catalog_id,
            MenuCatalog.company_id == company_id,
            MenuCatalog.is_active == True,
        )
        .first()
    )
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoria não encontrada")
    return category


def _assert_unique_category_name(
    db: Session,
    catalog_id: str,
    name: str,
    ignore_category_id: Optional[str] = None,
) -> None:
    query = (
        db.query(MenuCategory)
        .filter(MenuCategory.catalog_id == catalog_id, MenuCategory.name == name)
    )
    if ignore_category_id:
        query = query.filter(MenuCategory.id != ignore_category_id)
    if query.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma categoria com esse nome",
        )


def _assert_unique_sku(
    db: Session,
    catalog_id: str,
    sku: str,
    ignore_item_id: Optional[str] = None,
) -> None:
    query = (
        db.query(MenuItem)
        .filter(MenuItem.catalog_id == catalog_id, MenuItem.sku == sku)
    )
    if ignore_item_id:
        query = query.filter(MenuItem.id != ignore_item_id)
    if query.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um item com esse SKU",
        )


def _serialize_category(category: MenuCategory, items_count: int) -> dict[str, Any]:
    return {
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "sort_order": category.sort_order or 0,
        "items_count": items_count,
        "created_at": category.created_at,
        "updated_at": category.updated_at,
    }


def _serialize_item(item: MenuItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "category_id": item.category_id,
        "name": item.name,
        "description": item.description,
        "price": item.price,
        "is_available": bool(item.is_available),
        "custom_attributes": item.custom_attributes or [],
        "sku": item.sku,
        "stock_quantity": item.stock_quantity or 0,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }
