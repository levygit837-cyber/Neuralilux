"""Sincroniza o Catalog da Company Macedos a partir do JSON do cardápio."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import structlog
from sqlalchemy.orm import Session

from app.agent.clock import company_zone
from app.models import BusinessType, Company, MenuCatalog, MenuCategory, MenuItem
from app.services.menu.availability import capture_time, item_is_available
from app.services.menu.snapshot import (
    DEFAULT_MENU_JSON_PATH,
    MACEDOS_CATALOG_NAME,
    MACEDOS_COMPANY_DISPLAY_NAME,
    MACEDOS_COMPANY_NAME,
    load_menu_payload,
    parse_price,
)

logger = structlog.get_logger()


def _ensure_restaurant_business_type(db: Session) -> Optional[BusinessType]:
    business_type = db.query(BusinessType).filter(BusinessType.slug == "restaurant").first()
    if business_type:
        return business_type

    business_type = BusinessType(
        name="Restaurante",
        slug="restaurant",
        description="Estabelecimentos de alimentação e gastronomia",
        icon="restaurant",
    )
    db.add(business_type)
    db.flush()
    return business_type


def _ensure_macedos_company(db: Session, payload: dict[str, Any]) -> Company:
    company = db.query(Company).filter(Company.name == MACEDOS_COMPANY_NAME).first()
    if company:
        return company

    business_type = _ensure_restaurant_business_type(db)
    store = payload.get("store", {})

    company = Company(
        name=MACEDOS_COMPANY_NAME,
        business_type_id=business_type.id if business_type else None,
        description=store.get("name") or MACEDOS_COMPANY_DISPLAY_NAME,
        whatsapp=str(store.get("whatsapp") or "") or None,
        phone=str(store.get("phone") or "") or None,
        is_active=True,
    )
    db.add(company)
    db.flush()
    return company


def sync_macedos_menu_from_json(
    db: Session,
    json_path: Path = DEFAULT_MENU_JSON_PATH,
) -> MenuCatalog:
    payload = load_menu_payload(json_path)
    company = _ensure_macedos_company(db, payload)
    captured_local = capture_time(payload, company_zone(company))

    catalog = (
        db.query(MenuCatalog)
        .filter(MenuCatalog.company_id == company.id, MenuCatalog.name == MACEDOS_CATALOG_NAME)
        .first()
    )
    if not catalog:
        catalog = MenuCatalog(
            company_id=company.id,
            name=MACEDOS_CATALOG_NAME,
            source_type="json",
            source_file=str(json_path),
            is_active=True,
        )
        db.add(catalog)
        db.flush()
    else:
        catalog.source_type = "json"
        catalog.source_file = str(json_path)
        catalog.is_active = True

    db.query(MenuItem).filter(MenuItem.catalog_id == catalog.id).delete(synchronize_session=False)
    db.query(MenuCategory).filter(MenuCategory.catalog_id == catalog.id).delete(synchronize_session=False)
    db.flush()

    for category_index, category in enumerate(payload.get("categories", []), start=1):
        menu_category = MenuCategory(
            catalog_id=catalog.id,
            external_id=str(category.get("id") or category_index),
            name=(category.get("name") or "").strip(),
            description=(category.get("description") or "").strip() or None,
            sort_order=int(category.get("view_order") or category_index),
            raw_payload=category,
        )
        db.add(menu_category)
        db.flush()

        for item_index, item in enumerate(category.get("items") or [], start=1):
            db.add(
                MenuItem(
                    catalog_id=catalog.id,
                    category_id=menu_category.id,
                    external_id=str(item.get("id") or f"{menu_category.external_id}-{item_index}"),
                    name=(item.get("name") or "").strip(),
                    description=(item.get("description") or "").strip() or None,
                    price=parse_price(item.get("price") or item.get("numeric_price") or item.get("base_price")),
                    image_url=(item.get("image_url") or item.get("cover_photo") or "").strip() or None,
                    is_available=item_is_available(item, captured_local),
                    sort_order=int(item.get("view_order") or item_index),
                    raw_payload=item,
                )
            )

    db.commit()
    db.refresh(catalog)

    logger.info(
        "Macedos menu synchronized",
        company_id=company.id,
        catalog_id=catalog.id,
        categories=len(payload.get("categories", [])),
        items=sum(len(category.get("items") or []) for category in payload.get("categories", [])),
    )

    return catalog
