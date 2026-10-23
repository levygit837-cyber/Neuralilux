from decimal import Decimal

import pytest
from pack_helpers import add_item, call, confirm_and_finalize, fill_delivery, make_world, order_of, payload, tool_named

from app.models import CustomerOrder, PaymentRecord
from app.packs.catalog_orders.pack import CatalogOrdersPack

pytestmark = pytest.mark.asyncio


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def pedido(world):
    return tool_named(CatalogOrdersPack().tools(), "gerenciar_pedido")


# ---------- validação de dados ----------


@pytest.mark.parametrize("nome", ["retirada", "Pix", "  ENTREGA ", "a", "12", "ok", "dinheiro"])
async def test_invalid_names_are_refused(world, pedido, nome):
    await add_item(world, pedido)
    result = await call(pedido, world.ctx, acao="definir_dados", nome=nome)
    assert result.is_error
    assert order_of(world).customer_name is None


async def test_valid_name_is_stored(world, pedido):
    await add_item(world, pedido)
    result = await call(pedido, world.ctx, acao="definir_dados", nome="Zé")
    assert not result.is_error
    assert order_of(world).customer_name == "Zé"


@pytest.mark.parametrize("endereco", ["Rua A 1", "Rua das Flores sem numero", "12345678", "centro"])
async def test_invalid_delivery_addresses_are_refused(world, pedido, endereco):
    await add_item(world, pedido)
    result = await call(pedido, world.ctx, acao="definir_dados", tipo_entrega="entrega", endereco=endereco)
    assert result.is_error


async def test_address_not_required_for_pickup(world, pedido):
    await add_item(world, pedido)
    result = await call(pedido, world.ctx, acao="definir_dados", tipo_entrega="retirada", nome="Maria")
    assert not result.is_error
    assert payload(result)["pedido"]["faltando"] == ["forma_pagamento"]


async def test_invalid_enums_are_refused(world, pedido):
    await add_item(world, pedido)
    assert (await call(pedido, world.ctx, acao="definir_dados", forma_pagamento="boleto")).is_error
    assert (await call(pedido, world.ctx, acao="definir_dados", tipo_entrega="drone")).is_error


async def test_invalid_field_saves_nothing(world, pedido):
    await add_item(world, pedido)
    result = await call(pedido, world.ctx, acao="definir_dados", nome="Maria", forma_pagamento="boleto")
    assert result.is_error
    assert order_of(world).customer_name is None


async def test_definir_dados_without_order_is_error(world, pedido):
    assert (await call(pedido, world.ctx, acao="definir_dados", nome="Maria")).is_error


async def test_pix_payment_is_refused_early_when_company_has_no_key(db):
    world = make_world(db, pix_key=None)
    pedido = tool_named(CatalogOrdersPack().tools(), "gerenciar_pedido")
    await add_item(world, pedido)
    assert (await fill_delivery(world, pedido, forma_pagamento="pix")).is_error


# ---------- total, taxa e mínimo ----------


async def test_total_includes_zone_fee_for_delivery(world, pedido):
    await add_item(world, pedido)
    await fill_delivery(world, pedido)
    data = payload(await call(pedido, world.ctx, acao="ver"))["pedido"]
    assert data["subtotal"] == 45.0
    assert data["taxa_entrega"] == 5.0
    assert data["total"] == 50.0
    assert order_of(world).total_amount == Decimal("50.00")


async def test_pickup_has_no_fee(world, pedido):
    await add_item(world, pedido)
    await fill_delivery(world, pedido, tipo_entrega="retirada", endereco=None)
    data = payload(await call(pedido, world.ctx, acao="ver"))["pedido"]
    assert data["taxa_entrega"] == 0 and data["total"] == 45.0


async def test_zone_of_other_company_or_legacy_is_not_used(world, pedido):
    await add_item(world, pedido)
    for bairro in ("Praia", "Meireles"):
        result = await fill_delivery(world, pedido, endereco=f"Rua do Mar 500, {bairro}")
        assert result.is_error
        assert "bairro" in payload(result)["erro"].lower()


async def test_delivery_without_configured_zone_is_unavailable(db):
    world = make_world(db, with_zone=False)
    pedido = tool_named(CatalogOrdersPack().tools(), "gerenciar_pedido")
    await add_item(world, pedido)
    result = await fill_delivery(world, pedido)
    assert result.is_error
    assert "retirada" in payload(result)["erro"].lower()


async def test_minimum_order_blocks_finalize_and_counts_items_only(world, pedido):
    await add_item(world, pedido, name="Suco de Laranja")  # 9.50 < mínimo 30
    await fill_delivery(world, pedido)
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error
    assert "30" in payload(result)["erro"]
    assert order_of(world).status != "closed"


# ---------- finalizar ----------


async def test_finalize_requires_complete_data(world, pedido):
    await add_item(world, pedido)
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error
    err = payload(result)["erro"]
    assert "nome" in err and "tipo_entrega" in err and "forma_pagamento" in err


async def test_finalize_delivery_requires_address(world, pedido):
    await add_item(world, pedido)
    await call(pedido, world.ctx, acao="definir_dados", nome="Maria", tipo_entrega="entrega", forma_pagamento="cartao")
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error and "endereco" in payload(result)["erro"]


async def test_finalize_without_items_is_error(world, pedido):
    assert (await call(pedido, world.ctx, acao="finalizar")).is_error


async def test_finalize_cash_closes_order_with_total(world, pedido):
    await add_item(world, pedido)
    await fill_delivery(world, pedido, troco_para=100)
    result = await confirm_and_finalize(world, pedido)
    assert not result.is_error
    data = payload(result)
    assert data["pedido"]["status"] == "closed"
    assert data["pedido"]["total"] == 50.0
    assert data["pedido"]["troco_para"] == 100.0
    assert "pix" not in data
    order = order_of(world)
    assert order.status == "closed" and order.closed_at is not None
    assert order.customer_phone == world.contact.phone_number
    assert world.db.query(PaymentRecord).count() == 0


async def test_change_must_cover_total(world, pedido):
    await add_item(world, pedido)
    result = await fill_delivery(world, pedido, troco_para=20)
    assert result.is_error
    result = await fill_delivery(world, pedido, forma_pagamento="cartao", troco_para=100)
    assert result.is_error


async def test_after_finalize_a_new_order_starts_empty(world, pedido):
    await add_item(world, pedido)
    await fill_delivery(world, pedido)
    await confirm_and_finalize(world, pedido)
    assert payload(await call(pedido, world.ctx, acao="ver"))["pedido"] is None
    await add_item(world, pedido, name="Suco de Laranja")
    assert world.db.query(CustomerOrder).count() == 2
