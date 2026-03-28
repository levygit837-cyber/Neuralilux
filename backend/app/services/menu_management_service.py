from __future__ import annotations

from collections import Counter
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.models import MenuCatalog, MenuCategory, MenuItem
from app.schemas.menu import MenuCategoryCreate, MenuCategoryUpdate, MenuItemCreate, MenuItemUpdate


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
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


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

    db.query(MenuItem).filter(MenuItem.category_id == category.id).delete(synchronize_session=False)
    db.delete(category)
    db.commit()


def create_menu_item(db: Session, company_id: Optional[str], payload: MenuItemCreate) -> dict[str, Any]:
    resolved_company_id = _ensure_company_id(company_id)
    catalog = get_or_create_active_catalog(db, resolved_company_id)
    _promote_catalog_to_manual(catalog)
    category = _get_category_in_catalog(db, resolved_company_id, catalog.id, payload.category_id)

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

    db.commit()
    db.refresh(item)
    return _serialize_item(item)


def delete_menu_item(db: Session, company_id: Optional[str], item_id: str) -> None:
    resolved_company_id = _ensure_company_id(company_id)
    catalog, item = _get_item_for_company(db, resolved_company_id, item_id)
    _promote_catalog_to_manual(catalog)
    db.delete(item)
    db.commit()
