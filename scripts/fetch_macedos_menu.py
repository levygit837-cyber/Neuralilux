#!/usr/bin/env python3
"""
Fetch the public Macedos menu from Delivery Direto and export it as JSON.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://deliverydireto.com.br/pizzariamacedos/pizzariamacedos"
BASIC_INFO_URL = "https://deliverydireto.com.br/pizzariamacedos/basic_info"
STORE_ID = 4663
SOURCE_URL = f"{BASE_URL}?dd=menu"
DEFAULT_OUTPUT = Path("output/macedos_cardapio.json")
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)


def fetch_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if params:
        query = urlencode(params)
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{query}"

    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})

    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"HTTP error while fetching {url}: {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while fetching {url}: {exc.reason}") from exc


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def normalize_store(brand_payload: dict[str, Any]) -> dict[str, Any]:
    brand = brand_payload["brand"]
    store = brand["stores"][0]
    address = store["address"]

    return {
        "brand_id": brand["id"],
        "store_id": store["id"],
        "name": clean_text(store["name"]),
        "company_name": clean_text(store.get("company_name")),
        "document": store.get("document"),
        "minimum_order": store.get("minimum_order"),
        "takeout_minimum_order": store.get("takeout_minimum_order"),
        "formatted_minimum_order": store.get("formatted_minimum_order"),
        "formatted_takeout_minimum_order": store.get("formatted_takeout_minimum_order"),
        "formatted_contact_telephone": store.get("formatted_contact_telephone"),
        "formatted_url": store.get("formatted_url"),
        "formatted_virtual_menu_url": store.get("formatted_virtual_menu_url"),
        "legal_terms_url": store.get("legal_terms_url"),
        "social_links": {
            "facebook": store.get("url_facebook"),
            "instagram": store.get("url_instagram"),
            "twitter": store.get("url_twitter"),
            "tiktok": store.get("url_tiktok"),
        },
        "address": {
            "street": address.get("street"),
            "number": address.get("number"),
            "neighborhood": address.get("neighborhood"),
            "city": address.get("city"),
            "state": address.get("state"),
            "zip_code": address.get("zip_code"),
            "complement": address.get("complement"),
            "full_formatted_address": address.get("full_formatted_address"),
        },
        "business_hours": store.get("formatted_business_hours", []),
        "delivery_status": store.get("delivery_status"),
        "takeout_status": store.get("takeout_status"),
        "table_status": store.get("table_status"),
        "is_open_now": store.get("is_open_now"),
        "can_order": store.get("can_order"),
        "online_menu_pdf_url": store.get("settings", {}).get("online_menu_pdf_url"),
    }


def normalize_item(item: dict[str, Any], category_name: str) -> dict[str, Any]:
    normalized = dict(item)
    normalized["name"] = clean_text(item.get("name"))
    normalized["description"] = clean_text(item.get("description"))
    normalized["category_name"] = category_name
    normalized["order_types"] = [
        {
            "id": order_type.get("id"),
            "name": order_type.get("name"),
            "tag": order_type.get("tag"),
            "type": order_type.get("type"),
        }
        for order_type in item.get("filters", [])
    ]
    normalized["image_url"] = item.get("full_cover_photo") or item.get("cover_photo")
    return normalized


def build_menu_database() -> dict[str, Any]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    basic_info = fetch_json(BASIC_INFO_URL, {"per_page": 1, "stores_id": STORE_ID})
    categories_payload = fetch_json(f"{BASE_URL}/categories", {"webview": "false"})
    category_summaries = categories_payload["data"]["categories"]

    categories: list[dict[str, Any]] = []
    flat_items: list[dict[str, Any]] = []
    discrepancies: list[dict[str, Any]] = []

    for summary in category_summaries:
        detail_payload = fetch_json(
            f"{BASE_URL}/categories/{summary['id']}",
            {"include": "items,properties", "webview": "false"},
        )
        detail = detail_payload["data"]["category"]
        category_name = clean_text(detail.get("name") or summary.get("name"))
        normalized_items = [normalize_item(item, category_name) for item in detail.get("items", [])]

        category = dict(detail)
        category["name"] = category_name
        category["description"] = clean_text(detail.get("description"))
        category["listed_total"] = summary.get("total", 0)
        category["extracted_total"] = len(normalized_items)
        category["has_total_discrepancy"] = category["listed_total"] != category["extracted_total"]
        category["items"] = normalized_items
        category["summary_source"] = {
            "id": summary.get("id"),
            "encoded_name": summary.get("encoded_name"),
            "view_order": summary.get("view_order"),
            "show_on_mobile": summary.get("show_on_mobile"),
            "hidden_when_unavailable": summary.get("hidden_when_unavailable"),
            "has_visible_items": summary.get("has_visible_items"),
            "total": summary.get("total"),
        }

        if category["has_total_discrepancy"]:
            discrepancies.append(
                {
                    "category_id": category["id"],
                    "category_name": category["name"],
                    "listed_total": category["listed_total"],
                    "extracted_total": category["extracted_total"],
                }
            )

        categories.append(category)
        flat_items.extend(normalized_items)

    categories.sort(key=lambda item: item.get("view_order") or 0)
    flat_items.sort(key=lambda item: (item.get("category_id") or 0, item.get("view_order") or 0))

    return {
        "source": {
            "site_url": SOURCE_URL,
            "api_base_url": basic_info["data"]["api_base_url"],
            "fetched_at_utc": fetched_at,
            "provider": "Delivery Direto",
        },
        "store": normalize_store(basic_info["data"]),
        "summary": {
            "category_count": len(categories),
            "listed_item_count": sum(category.get("listed_total", 0) for category in categories),
            "extracted_item_count": len(flat_items),
            "item_count_discrepancies": discrepancies,
        },
        "categories": categories,
        "items_flat": flat_items,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Macedos menu as JSON.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    database = build_menu_database()
    args.output.write_text(
        json.dumps(database, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Wrote {database['summary']['extracted_item_count']} items in "
        f"{database['summary']['category_count']} categories to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
