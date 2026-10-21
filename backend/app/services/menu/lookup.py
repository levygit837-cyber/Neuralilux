"""Consulta o cardápio: snapshot do banco (com fallback no JSON) e busca de itens e categorias."""
from __future__ import annotations

from typing import Iterable, Optional

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Company, MenuCatalog, MenuCategory, MenuItem
from app.services.menu.snapshot import (
    MACEDOS_CATALOG_NAME,
    MACEDOS_COMPANY_NAME,
    MenuCategoryRecord,
    MenuItemRecord,
    MenuSnapshot,
    build_menu_snapshot_from_json,
    normalize_text,
)
from app.services.menu.sync import sync_macedos_menu_from_json

logger = structlog.get_logger()


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
