import json
from datetime import datetime, timedelta, timezone

import pytest
from pack_helpers import call, make_world, payload, tool_named

from app.models import MenuItem
from app.packs.catalog_orders.pack import CatalogOrdersPack

pytestmark = pytest.mark.asyncio


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def buscar(world):
    return tool_named(CatalogOrdersPack().tools(), "buscar_cardapio")


def names(result) -> list[str]:
    return [i["nome"] for i in payload(result)["itens"]]


async def test_multi_word_query_finds_item(world, buscar):
    result = await call(buscar, world.ctx, consulta="pizza toscana")
    assert names(result)[0] == "Pizza Toscana"
    item = payload(result)["itens"][0]
    assert item["id"] == world.items["Pizza Toscana"].id
    assert item["preco"] == 45.0
    assert item["descricao"] == "Calabresa, cebola e mussarela"


async def test_scope_is_the_context_company_not_a_hardcoded_name(world, buscar):
    result = await call(buscar, world.ctx, consulta="pizza toscana")
    assert [i["id"] for i in payload(result)["itens"]][0] == world.items["Pizza Toscana"].id
    assert world.other_company_item.id not in result.content


async def test_accent_and_case_insensitive(world, buscar):
    assert names(await call(buscar, world.ctx, consulta="REFRIGERANTE cola"))[0] == "Refrigerante Cola 2L"
    assert names(await call(buscar, world.ctx, consulta="suco laranja"))[0] == "Suco de Laranja"
    assert names(await call(buscar, world.ctx, consulta="Súco de Láranja"))[0] == "Suco de Laranja"


async def test_whole_word_match_pizza_does_not_hit_pizzaiolo(world, buscar):
    found = names(await call(buscar, world.ctx, consulta="pizza"))
    assert "Camiseta Pizzaiolo" not in found
    assert set(found) == {"Pizza Toscana", "Pizza Calabresa"}


async def test_simple_plural(world, buscar):
    assert set(names(await call(buscar, world.ctx, consulta="pizzas"))) == {"Pizza Toscana", "Pizza Calabresa"}
    assert names(await call(buscar, world.ctx, consulta="sucos")) == ["Suco de Laranja"]


async def test_unknown_word_does_not_hide_the_word_that_matches(world, buscar):
    assert names(await call(buscar, world.ctx, consulta="xyzzy toscana")) == ["Pizza Toscana"]
    assert names(await call(buscar, world.ctx, consulta="toscana xyzzy")) == ["Pizza Toscana"]


async def test_item_matching_more_words_comes_before_one_matching_fewer(world, buscar):
    found = names(await call(buscar, world.ctx, consulta="pizza toscana"))
    assert found[0] == "Pizza Toscana"
    assert set(found) == {"Pizza Toscana", "Pizza Calabresa"}


async def test_nothing_matches_when_no_word_exists(world, buscar):
    assert names(await call(buscar, world.ctx, consulta="xyzzy plugh")) == []


async def test_filler_words_do_not_count(world, buscar):
    # "uma", "de" não casam nada: só "pizza" e "calabresa" pontuam.
    assert names(await call(buscar, world.ctx, consulta="uma pizza de calabresa"))[0] == "Pizza Calabresa"


async def test_pizza_de_calabresa_finds_the_calabresa_pizza_first(world, buscar):
    found = names(await call(buscar, world.ctx, consulta="pizza de calabresa"))
    assert found[0] == "Pizza Calabresa"
    # Toscana leva calabresa na descrição: entra, mas atrás da que tem a palavra no nome.
    assert found.index("Pizza Toscana") > 0


async def test_more_matched_words_rank_first(world, buscar):
    found = names(await call(buscar, world.ctx, consulta="suco de bebida"))
    assert found == ["Suco de Laranja", "Refrigerante Cola 2L"]


async def test_coca_2_litros_brings_the_cocas(db):
    from decimal import Decimal

    from app.models import MenuCategory, MenuItem

    world = make_world(db)
    catalog_id = world.items["Pizza Toscana"].catalog_id
    drinks = db.query(MenuCategory).filter_by(catalog_id=catalog_id, name="Bebidas").one()
    for name, description in [("COCA COLA", "1,5 LT"), ("COCA COLA ZERO", "1,5 LT"), ("GUARANÁ ANTARTICA", "LATA 350 ML")]:
        db.add(MenuItem(catalog_id=catalog_id, category_id=drinks.id, name=name, price=Decimal("19.00"), description=description))
    db.commit()

    found = names(await call(tool_named(CatalogOrdersPack().tools(), "buscar_cardapio"), world.ctx, consulta="coca 2 litros"))
    assert found[:2] == ["COCA COLA", "COCA COLA ZERO"]
    assert "Pizza Toscana" not in found


async def test_generic_category_name_finds_the_category(world, buscar):
    assert set(names(await call(buscar, world.ctx, consulta="refrigerante"))) >= {"Refrigerante Cola 2L", "Suco de Laranja"}
    assert set(names(await call(buscar, world.ctx, consulta="bebida"))) == {"Refrigerante Cola 2L", "Suco de Laranja"}


async def test_category_synonym_massa_finds_pastas(db):
    from decimal import Decimal

    from app.models import MenuCategory, MenuItem

    world = make_world(db)
    catalog_id = world.items["Pizza Toscana"].catalog_id
    pastas = MenuCategory(catalog_id=catalog_id, name="Pastas", sort_order=5)
    db.add(pastas)
    db.flush()
    db.add(MenuItem(catalog_id=catalog_id, category_id=pastas.id, name="Rondelli", price=Decimal("98.00")))
    db.commit()

    buscar = tool_named(CatalogOrdersPack().tools(), "buscar_cardapio")
    assert names(await call(buscar, world.ctx, consulta="massa")) == ["Rondelli"]
    assert names(await call(buscar, world.ctx, categoria="massas")) == ["Rondelli"]


async def test_query_matches_category_name(world, buscar):
    assert set(names(await call(buscar, world.ctx, consulta="bebidas"))) == {"Refrigerante Cola 2L", "Suco de Laranja"}


async def test_categoria_filter(world, buscar):
    assert set(names(await call(buscar, world.ctx, categoria="bebida"))) == {"Refrigerante Cola 2L", "Suco de Laranja"}
    assert names(await call(buscar, world.ctx, consulta="cola", categoria="bebidas")) == ["Refrigerante Cola 2L"]
    assert names(await call(buscar, world.ctx, consulta="cola", categoria="pizzas")) == []


async def test_unavailable_items_are_never_returned(world, buscar):
    assert names(await call(buscar, world.ctx, consulta="portuguesa")) == []
    assert "Pizza Portuguesa" not in names(await call(buscar, world.ctx, categoria="pizzas"))


async def test_result_is_capped_at_15(db):
    from decimal import Decimal

    from app.models import MenuCategory, MenuItem

    world = make_world(db)
    catalog_id = world.items["Pizza Toscana"].catalog_id
    category = MenuCategory(catalog_id=catalog_id, name="Esfihas", sort_order=9)
    db.add(category)
    db.flush()
    for n in range(20):
        db.add(MenuItem(catalog_id=catalog_id, category_id=category.id, name=f"Esfiha {n}", price=Decimal("5.00")))
    db.commit()

    result = await call(tool_named(CatalogOrdersPack().tools(), "buscar_cardapio"), world.ctx, consulta="esfiha")
    data = payload(result)
    assert len(data["itens"]) == 15
    assert data["total_encontrado"] == 20


async def test_description_is_shortened(db):
    world = make_world(db)
    world.items["Pizza Calabresa"].description = "x" * 400
    db.commit()
    result = await call(tool_named(CatalogOrdersPack().tools(), "buscar_cardapio"), world.ctx, consulta="calabresa")
    assert len(payload(result)["itens"][0]["descricao"]) <= 120


async def test_inactive_catalog_is_ignored(world, buscar):
    from app.models import MenuCatalog

    catalog = world.db.query(MenuCatalog).filter_by(company_id=world.company.id).one()
    catalog.is_active = False
    world.db.commit()
    assert names(await call(buscar, world.ctx, consulta="pizza")) == []


async def test_empty_search_lists_categories_with_counts_and_no_items(world, buscar):
    data = payload(await call(buscar, world.ctx))
    # Pizza Portuguesa está indisponível e não entra na contagem.
    assert data["categorias"] == [
        {"nome": "Pizzas", "itens": 2},
        {"nome": "Bebidas", "itens": 2},
        {"nome": "Brindes", "itens": 1},
    ]
    assert data["itens"] == []


async def test_query_of_only_filler_words_is_an_empty_search(world, buscar):
    assert payload(await call(buscar, world.ctx, consulta="de uma"))["itens"] == []


NIGHT_ONLY = [{"weekday": d, "period_start": "18:00", "period_end": "22:59"} for d in range(1, 8)]


def _scheduled_pizza(world, windows=NIGHT_ONLY):
    world.items["Pizza Toscana"].raw_payload = {"items_availability": windows}
    world.db.commit()


def _at(monkeypatch, local: datetime):
    from app.agent import clock

    # A Company do world está em America/Fortaleza (UTC-3, sem horário de verão).
    monkeypatch.setattr(clock, "utc_now", lambda: local.replace(tzinfo=timezone.utc) + timedelta(hours=3))


async def _toscana(world, buscar):
    return payload(await call(buscar, world.ctx, consulta="pizza toscana"))["itens"][0]


THURSDAY = datetime(2026, 10, 22)


async def test_item_outside_its_own_window_comes_with_when_it_is_sold(world, buscar, monkeypatch):
    _scheduled_pizza(world)
    _at(monkeypatch, THURSDAY.replace(hour=14))
    assert (await _toscana(world, buscar))["disponibilidade"] == "Fora do horário agora; disponível a partir de hoje às 18:00."


async def test_item_inside_its_window_has_no_notice_up_to_the_last_minute(world, buscar, monkeypatch):
    _scheduled_pizza(world)
    _at(monkeypatch, THURSDAY.replace(hour=22, minute=59))
    assert "disponibilidade" not in await _toscana(world, buscar)


async def test_after_tonight_window_the_notice_points_to_tomorrow(world, buscar, monkeypatch):
    _scheduled_pizza(world)
    _at(monkeypatch, THURSDAY.replace(hour=23))
    assert (await _toscana(world, buscar))["disponibilidade"].endswith("a partir de amanhã às 18:00.")


async def test_window_crossing_midnight_still_sells_in_the_early_hours(world, buscar, monkeypatch):
    # weekday 4 = quarta (1 = domingo): quarta 18:00 até quinta 02:00.
    _scheduled_pizza(world, [{"weekday": 4, "period_start": "18:00", "period_end": "02:00"}])
    _at(monkeypatch, THURSDAY.replace(hour=1, minute=30))
    assert "disponibilidade" not in await _toscana(world, buscar)
    _at(monkeypatch, THURSDAY.replace(hour=3))
    assert (await _toscana(world, buscar))["disponibilidade"].endswith("a partir de quarta-feira às 18:00.")


def _menu_json(tmp_path, items, fetched_at="2026-03-27T16:56:48+00:00"):  # sexta 13:56 em São Paulo
    path = tmp_path / "cardapio.json"
    path.write_text(json.dumps({"source": {"fetched_at_utc": fetched_at}, "categories": [{"id": 1, "name": "X", "items": items}]}))
    return path


def _menu_item(item_id, *, available, windows):
    return {"id": item_id, "name": f"Item {item_id}", "price": "10,00", "is_available": available, "items_availability": windows}


async def test_sync_keeps_items_that_were_only_outside_their_window_at_capture(db, tmp_path):
    from app.services.menu.sync import sync_macedos_menu_from_json

    all_day = [{"weekday": d, "period_start": "00:00", "period_end": "23:59"} for d in range(1, 8)]
    path = _menu_json(
        tmp_path,
        [
            _menu_item(1, available=False, windows=NIGHT_ONLY),  # pizza capturada de dia
            _menu_item(2, available=False, windows=all_day),  # pausado com a captura dentro da janela
            _menu_item(3, available=False, windows=[]),
            _menu_item(4, available=True, windows=all_day),
        ],
    )
    catalog = sync_macedos_menu_from_json(db, path)
    saved = {i.external_id: i.is_available for i in db.query(MenuItem).filter(MenuItem.catalog_id == catalog.id)}
    assert saved == {"1": True, "2": False, "3": False, "4": True}


async def test_sync_trusts_the_flag_when_capture_time_is_unknown(db, tmp_path):
    from app.services.menu.sync import sync_macedos_menu_from_json

    catalog = sync_macedos_menu_from_json(db, _menu_json(tmp_path, [_menu_item(1, available=False, windows=NIGHT_ONLY)], fetched_at=None))
    assert db.query(MenuItem).filter(MenuItem.catalog_id == catalog.id).one().is_available is False
