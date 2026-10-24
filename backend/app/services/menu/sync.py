"""Importa o cardápio de uma Company a partir de um JSON (categorias e itens) para o Catalog dela."""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

import structlog
from sqlalchemy.orm import Session

from app.agent.clock import company_zone
from app.models import Company, MenuCatalog, MenuCategory, MenuItem
from app.services.menu.availability import capture_time, item_is_available

logger = structlog.get_logger()

DEFAULT_CATALOG_NAME = "Cardápio"


def parse_price(value: Any) -> Optional[Decimal]:
    if value in {None, ""}:
        return None
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"))

    raw_value = str(value).strip()
    raw_value = raw_value.replace("R$", "").replace("\xa0", "").replace(".", "").replace(",", ".")
    try:
        return Decimal(raw_value).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def load_menu_payload(json_path: Path) -> dict[str, Any]:
    with json_path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def sync_menu_from_json(
    db: Session,
    company: Company,
    json_path: Path,
    catalog_name: str = DEFAULT_CATALOG_NAME,
) -> MenuCatalog:
    """Substitui categorias e itens do Catalog `catalog_name` da Company pelo conteúdo do JSON."""
    payload = load_menu_payload(json_path)
    captured_local = capture_time(payload, company_zone(company))

    catalog = (
        db.query(MenuCatalog)
        .filter(MenuCatalog.company_id == company.id, MenuCatalog.name == catalog_name)
        .first()
    )
    if not catalog:
        catalog = MenuCatalog(
            company_id=company.id,
            name=catalog_name,
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
        "Menu synchronized",
        company_id=company.id,
        catalog_id=catalog.id,
        categories=len(payload.get("categories", [])),
        items=sum(len(category.get("items") or []) for category in payload.get("categories", [])),
    )

    return catalog
