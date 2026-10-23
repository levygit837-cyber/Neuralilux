import json

from app.models import MenuItem
from app.services.menu.sync import sync_macedos_menu_from_json

NIGHT_ONLY = [{"weekday": d, "period_start": "18:00", "period_end": "22:59"} for d in range(1, 8)]
ALL_DAY = [{"weekday": d, "period_start": "00:00", "period_end": "23:59"} for d in range(1, 8)]
FRIDAY_AFTERNOON = "2026-03-27T16:56:48+00:00"  # sexta 13:56 em São Paulo


def _menu_json(tmp_path, items, fetched_at=FRIDAY_AFTERNOON):
    path = tmp_path / "cardapio.json"
    category = {"id": 1, "name": "X", "items": items}
    path.write_text(json.dumps({"source": {"fetched_at_utc": fetched_at}, "categories": [category]}))
    return path


def _menu_item(item_id, *, available, windows):
    return {
        "id": item_id,
        "name": f"Item {item_id}",
        "price": "10,00",
        "is_available": available,
        "items_availability": windows,
    }


def _saved(db, catalog):
    return {i.external_id: i.is_available for i in db.query(MenuItem).filter(MenuItem.catalog_id == catalog.id)}


def test_sync_keeps_items_that_were_only_outside_their_window_at_capture(db, tmp_path):
    path = _menu_json(
        tmp_path,
        [
            _menu_item(1, available=False, windows=NIGHT_ONLY),  # pizza capturada de dia
            _menu_item(2, available=False, windows=ALL_DAY),  # pausado com a captura dentro da janela
            _menu_item(3, available=False, windows=[]),
            _menu_item(4, available=True, windows=ALL_DAY),
        ],
    )
    assert _saved(db, sync_macedos_menu_from_json(db, path)) == {"1": True, "2": False, "3": False, "4": True}


def test_sync_trusts_the_flag_when_capture_time_is_unknown(db, tmp_path):
    path = _menu_json(tmp_path, [_menu_item(1, available=False, windows=NIGHT_ONLY)], fetched_at=None)
    assert _saved(db, sync_macedos_menu_from_json(db, path)) == {"1": False}
