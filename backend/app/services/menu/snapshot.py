from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import structlog

from app.services.menu.availability import item_is_available


logger = structlog.get_logger()


def _discover_menu_json_path() -> Path:
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        candidate = parent / "output" / "macedos_cardapio.json"
        if candidate.exists():
            return candidate
    return current_file.parents[3] / "output" / "macedos_cardapio.json"


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
                    is_available=item_is_available(item),
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
