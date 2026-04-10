from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import BusinessType, Company, MenuCatalog, MenuCategory, MenuItem

logger = structlog.get_logger()


def _discover_menu_json_path() -> Path:
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        candidate = parent / "output" / "macedos_cardapio.json"
        if candidate.exists():
            return candidate
    return current_file.parents[2] / "output" / "macedos_cardapio.json"


DEFAULT_MENU_JSON_PATH = _discover_menu_json_path()
MACEDOS_COMPANY_NAME = "Macedos"
MACEDOS_COMPANY_DISPLAY_NAME = "Pizzaria Macedos"
MACEDOS_CATALOG_NAME = "Cardápio"


@dataclass(frozen=True)
class MenuCategoryRecord:
    id: str
    name: str
    description: Optional[str]
    sort_order: int


@dataclass(frozen=True)
class MenuItemRecord:
    id: str
    category_id: str
    category_name: str
    name: str
    description: Optional[str]
    price: Optional[Decimal]
    image_url: Optional[str]
    is_available: bool
    sort_order: int


@dataclass(frozen=True)
class MenuSnapshot:
    source: str
    company_name: str
    catalog_name: str
    categories: list[MenuCategoryRecord]
    items: list[MenuItemRecord]


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


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


@lru_cache(maxsize=4)
def _load_menu_payload_cached(json_path: str) -> dict[str, Any]:
    path = Path(json_path)
    with path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def load_menu_payload(json_path: Path = DEFAULT_MENU_JSON_PATH) -> dict[str, Any]:
    return _load_menu_payload_cached(str(json_path))


def build_menu_snapshot_from_json(json_path: Path = DEFAULT_MENU_JSON_PATH) -> MenuSnapshot:
    payload = load_menu_payload(json_path)
    categories: list[MenuCategoryRecord] = []
    items: list[MenuItemRecord] = []

    for fallback_index, category in enumerate(payload.get("categories", []), start=1):
        category_id = str(category.get("id") or fallback_index)
        category_name = (category.get("name") or "").strip()
        categories.append(
            MenuCategoryRecord(
                id=category_id,
                name=category_name,
                description=(category.get("description") or "").strip() or None,
                sort_order=int(category.get("view_order") or fallback_index),
            )
        )

        for item_index, item in enumerate(category.get("items") or [], start=1):
            items.append(
                MenuItemRecord(
                    id=str(item.get("id") or f"{category_id}-{item_index}"),
                    category_id=category_id,
                    category_name=category_name,
                    name=(item.get("name") or "").strip(),
                    description=(item.get("description") or "").strip() or None,
                    price=parse_price(item.get("price") or item.get("numeric_price") or item.get("base_price")),
                    image_url=(item.get("image_url") or item.get("cover_photo") or "").strip() or None,
                    is_available=bool(item.get("is_available_if_active", item.get("is_available", True))),
                    sort_order=int(item.get("view_order") or item_index),
                )
            )

    return MenuSnapshot(
        source="json",
        company_name=MACEDOS_COMPANY_NAME,
        catalog_name=MACEDOS_CATALOG_NAME,
        categories=sorted(categories, key=lambda category: (category.sort_order, normalize_text(category.name))),
        items=sorted(
            items,
            key=lambda item: (
                next(
                    (category.sort_order for category in categories if category.id == item.category_id),
                    9999,
                ),
                item.sort_order,
                normalize_text(item.name),
            ),
        ),
    )


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
        website=store.get("website") or None,
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
                    is_available=bool(item.get("is_available_if_active", item.get("is_available", True))),
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


def _build_menu_snapshot_from_db(db: Session) -> Optional[MenuSnapshot]:
    catalog = (
        db.query(MenuCatalog)
        .join(Company, Company.id == MenuCatalog.company_id)
        .filter(Company.name == MACEDOS_COMPANY_NAME, MenuCatalog.name == MACEDOS_CATALOG_NAME)
        .first()
    )
    if not catalog:
        return None

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

    return MenuSnapshot(
        source="db",
        company_name=MACEDOS_COMPANY_NAME,
        catalog_name=catalog.name,
        categories=[
            MenuCategoryRecord(
                id=category.id,
                name=category.name,
                description=category.description,
                sort_order=category.sort_order or 0,
            )
            for category in categories
        ],
        items=[
            MenuItemRecord(
                id=item.id,
                category_id=item.category_id,
                category_name=category_name,
                name=item.name,
                description=item.description,
                price=item.price,
                image_url=item.image_url,
                is_available=bool(item.is_available),
                sort_order=item.sort_order or 0,
            )
            for item, category_name in items
        ],
    )


def get_menu_snapshot(db: Session, allow_sync: bool = True) -> MenuSnapshot:
    try:
        snapshot = _build_menu_snapshot_from_db(db)
        if snapshot and snapshot.items:
            return snapshot

        if allow_sync:
            sync_macedos_menu_from_json(db)
            snapshot = _build_menu_snapshot_from_db(db)
            if snapshot and snapshot.items:
                return snapshot
    except SQLAlchemyError as exc:
        logger.warning("Failed to load Macedos menu from database", error=str(exc))
        db.rollback()
    except FileNotFoundError:
        raise
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Unexpected menu catalog error", error=str(exc))
        db.rollback()

    return build_menu_snapshot_from_json()


def find_matching_category_name(message: str, db: Optional[Session] = None) -> Optional[str]:
    snapshot = get_menu_snapshot(db, allow_sync=False) if db is not None else build_menu_snapshot_from_json()
    normalized_message = normalize_text(message)
    categories = sorted(snapshot.categories, key=lambda category: len(normalize_text(category.name)), reverse=True)

    for category in categories:
        normalized_category = normalize_text(category.name)
        if not normalized_category:
            continue
        if normalized_category in normalized_message:
            return category.name

        tokens = [token for token in normalized_category.split() if len(token) > 2]
        if tokens and all(token in normalized_message for token in tokens):
            return category.name

        singular_tokens = [token[:-1] if token.endswith("s") else token for token in tokens]
        if singular_tokens and all(token in normalized_message for token in singular_tokens):
            return category.name

    return None


def filter_items_by_category(items: Iterable[MenuItemRecord], category_name: str) -> list[MenuItemRecord]:
    target = normalize_text(category_name)
    return [
        item for item in items
        if normalize_text(item.category_name) == target or target in normalize_text(item.category_name)
    ]


def find_menu_item(item_name: str, db: Optional[Session] = None) -> Optional[MenuItemRecord]:
    snapshot = get_menu_snapshot(db, allow_sync=True) if db is not None else build_menu_snapshot_from_json()
    normalized_target = normalize_text(item_name)
    if not normalized_target:
        return None

    exact_available = []
    exact_unavailable = []
    partial_available = []
    partial_unavailable = []

    for item in snapshot.items:
        normalized_name = normalize_text(item.name)
        if not normalized_name:
            continue
        if normalized_name == normalized_target:
            if item.is_available:
                exact_available.append(item)
            else:
                exact_unavailable.append(item)
            continue
        if normalized_target in normalized_name:
            if item.is_available:
                partial_available.append(item)
            else:
                partial_unavailable.append(item)

    ordered_candidates = [
        sorted(exact_available, key=lambda item: (item.sort_order, normalize_text(item.name))),
        sorted(exact_unavailable, key=lambda item: (item.sort_order, normalize_text(item.name))),
        sorted(partial_available, key=lambda item: (item.sort_order, normalize_text(item.name))),
        sorted(partial_unavailable, key=lambda item: (item.sort_order, normalize_text(item.name))),
    ]
    for candidates in ordered_candidates:
        if candidates:
            return candidates[0]

    return None
