from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pack_helpers import add_item, call, fill_delivery, make_world, order_of, payload, tool_named

from app.models import Contact, Conversation, CustomerOrder, MenuCatalog
from app.packs.catalog_orders.pack import CatalogOrdersPack

pytestmark = pytest.mark.asyncio


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def pedido(world):
    return tool_named(CatalogOrdersPack().tools(), "gerenciar_pedido")


# ---------- adicionar_item ----------


async def test_add_item_uses_catalog_price_and_quantity(world, pedido):
    result = await add_item(world, pedido, quantidade=2, observacao="sem cebola")
    assert not result.is_error
    data = payload(result)["pedido"]
    assert data["subtotal"] == 90.0
    assert data["itens"][0]["quantidade"] == 2
    assert data["itens"][0]["observacao"] == "sem cebola"
    order = order_of(world)
    assert order.contact_id == world.contact.id and order.instance_id == world.instance.id
    assert order.total_amount == Decimal("90.00")


async def test_same_item_and_note_accumulates_quantity(world, pedido):
    await add_item(world, pedido, quantidade=1)
    await add_item(world, pedido, quantidade=2)
    items = payload(await call(pedido, world.ctx, acao="ver"))["pedido"]["itens"]
    assert len(items) == 1 and items[0]["quantidade"] == 3


async def test_unavailable_item_is_refused(world, pedido):
    result = await add_item(world, pedido, name="Pizza Portuguesa")
    assert result.is_error
    assert "indispon" in payload(result)["erro"].lower()
    assert world.db.query(CustomerOrder).count() == 0


async def test_item_from_other_company_is_refused(world, pedido):
    result = await call(pedido, world.ctx, acao="adicionar_item", item_id=world.other_company_item.id)
    assert result.is_error
    assert world.db.query(CustomerOrder).count() == 0


async def test_item_from_inactive_catalog_is_refused_like_the_search(world, pedido):
    catalog = world.db.query(MenuCatalog).filter_by(company_id=world.company.id).one()
    catalog.is_active = False
    world.db.commit()

    result = await add_item(world, pedido)
    assert result.is_error
    assert "cardápio" in payload(result)["erro"]
    assert world.db.query(CustomerOrder).count() == 0


async def test_unknown_item_and_bad_quantity_are_refused(world, pedido):
    assert (await call(pedido, world.ctx, acao="adicionar_item", item_id="nope")).is_error
    assert (await call(pedido, world.ctx, acao="adicionar_item")).is_error
    assert (await add_item(world, pedido, quantidade=0)).is_error
    assert (await add_item(world, pedido, quantidade=-1)).is_error


# ---------- remover_item ----------


async def test_remove_item_partial_and_total(world, pedido):
    await add_item(world, pedido, quantidade=3)
    await add_item(world, pedido, name="Suco de Laranja")
    item_id = world.items["Pizza Toscana"].id

    data = payload(await call(pedido, world.ctx, acao="remover_item", item_id=item_id, quantidade=1))["pedido"]
    assert [i["quantidade"] for i in data["itens"]] == [2, 1]
    assert data["subtotal"] == 99.5

    data = payload(await call(pedido, world.ctx, acao="remover_item", item_id=item_id))["pedido"]
    assert [i["nome"] for i in data["itens"]] == ["Suco de Laranja"]
    assert data["subtotal"] == 9.5


async def _three_lines_of_the_same_item(world, pedido):
    await add_item(world, pedido, quantidade=2, observacao="sem cebola")
    await add_item(world, pedido, quantidade=1)
    await add_item(world, pedido, quantidade=3, observacao="bem passada")
    return world.items["Pizza Toscana"].id


async def test_remove_quantity_spans_multiple_lines_of_the_same_item(world, pedido):
    item_id = await _three_lines_of_the_same_item(world, pedido)

    data = payload(await call(pedido, world.ctx, acao="remover_item", item_id=item_id, quantidade=4))["pedido"]

    # Desconta da linha mais recente para a mais antiga: some "bem passada" (3) e a linha sem nota (1).
    assert [(i["quantidade"], i["observacao"]) for i in data["itens"]] == [(2, "sem cebola")]
    assert data["subtotal"] == 90.0
    assert order_of(world).total_amount == Decimal("90.00")


async def test_remove_quantity_inside_the_last_line_keeps_the_others(world, pedido):
    item_id = await _three_lines_of_the_same_item(world, pedido)

    data = payload(await call(pedido, world.ctx, acao="remover_item", item_id=item_id, quantidade=2))["pedido"]

    assert [i["quantidade"] for i in data["itens"]] == [2, 1, 1]
    assert data["subtotal"] == 180.0


async def test_remove_more_than_ordered_clears_every_line_of_the_item(world, pedido):
    item_id = await _three_lines_of_the_same_item(world, pedido)
    await add_item(world, pedido, name="Suco de Laranja")

    data = payload(await call(pedido, world.ctx, acao="remover_item", item_id=item_id, quantidade=50))["pedido"]

    assert [i["nome"] for i in data["itens"]] == ["Suco de Laranja"]


async def test_remove_without_quantity_clears_every_line_of_the_item(world, pedido):
    item_id = await _three_lines_of_the_same_item(world, pedido)

    data = payload(await call(pedido, world.ctx, acao="remover_item", item_id=item_id))["pedido"]

    assert data["itens"] == [] and data["subtotal"] == 0


async def test_remove_item_not_in_order_is_error(world, pedido):
    await add_item(world, pedido)
    result = await call(pedido, world.ctx, acao="remover_item", item_id=world.items["Suco de Laranja"].id)
    assert result.is_error


async def test_ver_without_order_says_empty(world, pedido):
    result = await call(pedido, world.ctx, acao="ver")
    assert not result.is_error
    assert payload(result)["pedido"] is None


async def test_unknown_action_is_error(world, pedido):
    assert (await call(pedido, world.ctx, acao="iniciar_finalizacao")).is_error


# ---------- status_pedido ----------


async def test_status_without_orders(world):
    status = tool_named(CatalogOrdersPack().tools(), "status_pedido")
    result = await call(status, world.ctx)
    assert not result.is_error
    assert payload(result)["pedido"] is None


async def test_status_returns_latest_order_of_the_contact(world, pedido):
    status = tool_named(CatalogOrdersPack().tools(), "status_pedido")
    await add_item(world, pedido, name="Suco de Laranja")
    await fill_delivery(world, pedido, tipo_entrega="retirada", endereco=None)
    old = order_of(world)
    old.status = "delivered"
    old.opened_at = old.created_at = datetime.now(timezone.utc) - timedelta(days=2)
    world.db.commit()

    await add_item(world, pedido, quantidade=2)
    await fill_delivery(world, pedido)
    await call(pedido, world.ctx, acao="finalizar")
    last = payload(await call(status, world.ctx))["pedido"]
    assert last["status"] == "closed"
    assert last["total"] == 95.0
    assert [i["nome"] for i in last["itens"]] == ["Pizza Toscana"]

    world.db.expire_all()
    newest = world.db.query(CustomerOrder).order_by(CustomerOrder.opened_at.desc()).first()
    assert last["numero"] == newest.order_number


async def test_status_never_shows_orders_of_another_contact(world):
    other = Contact(instance_id=world.instance.id, phone_number="5585911112222", remote_jid="5585911112222@s.whatsapp.net")
    world.db.add(other)
    world.db.flush()
    conv = Conversation(instance_id=world.instance.id, contact_id=other.id, remote_jid=other.remote_jid)
    world.db.add(conv)
    world.db.flush()
    world.db.add(
        CustomerOrder(
            order_number="X-1",
            conversation_id=conv.id,
            instance_id=world.instance.id,
            contact_id=other.id,
            remote_jid=other.remote_jid,
            total_amount=Decimal("10"),
        )
    )
    world.db.commit()
    status = tool_named(CatalogOrdersPack().tools(), "status_pedido")
    assert payload(await call(status, world.ctx))["pedido"] is None


# ---------- contrato do Pack ----------


async def test_pack_exposes_exactly_three_tools_with_json_schema():
    pack = CatalogOrdersPack()
    assert pack.name == "catalog_orders"
    tools = pack.tools()
    assert [t.name for t in tools] == ["buscar_cardapio", "gerenciar_pedido", "status_pedido"]
    for t in tools:
        assert t.input_schema["type"] == "object"
        assert t.description


async def test_system_prompt_section_describes_the_order_flow(world):
    text = CatalogOrdersPack().system_prompt_section(world.ctx)
    for needle in ("buscar_cardapio", "gerenciar_pedido", "status_pedido", "finalizar", "transferir_atendente"):
        assert needle in text
