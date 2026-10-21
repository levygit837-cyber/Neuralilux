import pytest
from pack_helpers import call, make_world, payload, tool_named

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
    assert names(result) == ["Pizza Toscana"]
    item = payload(result)["itens"][0]
    assert item["id"] == world.items["Pizza Toscana"].id
    assert item["preco"] == 45.0
    assert item["descricao"] == "Calabresa, cebola e mussarela"


async def test_scope_is_the_context_company_not_a_hardcoded_name(world, buscar):
    result = await call(buscar, world.ctx, consulta="pizza toscana")
    assert [i["id"] for i in payload(result)["itens"]] == [world.items["Pizza Toscana"].id]
    assert world.other_company_item.id not in result.content


async def test_accent_and_case_insensitive(world, buscar):
    assert names(await call(buscar, world.ctx, consulta="REFRIGERANTE cola")) == ["Refrigerante Cola 2L"]
    assert names(await call(buscar, world.ctx, consulta="suco laranja")) == ["Suco de Laranja"]
    assert names(await call(buscar, world.ctx, consulta="Súco de Láranja")) == ["Suco de Laranja"]


async def test_whole_word_match_pizza_does_not_hit_pizzaiolo(world, buscar):
    found = names(await call(buscar, world.ctx, consulta="pizza"))
    assert "Camiseta Pizzaiolo" not in found
    assert set(found) == {"Pizza Toscana", "Pizza Calabresa"}


async def test_simple_plural(world, buscar):
    assert set(names(await call(buscar, world.ctx, consulta="pizzas"))) == {"Pizza Toscana", "Pizza Calabresa"}
    assert names(await call(buscar, world.ctx, consulta="sucos")) == ["Suco de Laranja"]


async def test_all_tokens_must_match(world, buscar):
    assert names(await call(buscar, world.ctx, consulta="pizza suco")) == []


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


async def test_empty_search_lists_categories_and_first_items(world, buscar):
    data = payload(await call(buscar, world.ctx))
    assert data["categorias"] == ["Pizzas", "Bebidas", "Brindes"]
    assert data["itens"][0]["nome"] in {"Pizza Toscana", "Pizza Calabresa"}
