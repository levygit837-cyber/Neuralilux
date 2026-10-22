"""Fechamento confiável do Order (#32): recapitulação, adição idempotente e Company fechada."""

from datetime import datetime, timezone

import pytest
from pack_helpers import add_item, call, confirm_and_finalize, fill_delivery, make_world, new_turn, order_of, payload, tool_named

from app.packs.catalog_orders import checkout
from app.packs.catalog_orders.pack import CatalogOrdersPack

pytestmark = pytest.mark.asyncio


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def pedido(world):
    return tool_named(CatalogOrdersPack().tools(), "gerenciar_pedido")


async def ready_order(world, pedido, **overrides):
    await add_item(world, pedido)
    await add_item(world, pedido, name="Suco de Laranja")
    await fill_delivery(world, pedido, **overrides)


# ---------- recapitulação antes de fechar ----------


async def test_finalize_without_recap_is_refused(world, pedido):
    await ready_order(world, pedido)
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error
    assert "recapitular" in payload(result)["erro"]
    assert order_of(world).status != "closed"


async def test_finalize_in_the_same_turn_as_the_recap_is_refused(world, pedido):
    await ready_order(world, pedido)
    assert not (await call(pedido, world.ctx, acao="recapitular")).is_error
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error
    assert order_of(world).status != "closed"


async def test_finalize_after_recap_in_a_previous_turn_closes_the_order(world, pedido):
    await ready_order(world, pedido)
    result = await confirm_and_finalize(world, pedido)
    assert not result.is_error
    assert payload(result)["pedido"]["status"] == "closed"
    assert order_of(world).status == "closed"


async def test_recap_returns_the_order_with_the_real_total(world, pedido):
    await ready_order(world, pedido)
    data = payload(await call(pedido, world.ctx, acao="recapitular"))
    assert data["pedido"]["total"] == 59.5  # 45 + 9.50 dos itens + 5 de taxa


async def test_recap_of_an_incomplete_order_is_refused_and_does_not_unlock_finalize(world, pedido):
    await add_item(world, pedido)
    result = await call(pedido, world.ctx, acao="recapitular")
    assert result.is_error and "nome" in payload(result)["erro"]
    await fill_delivery(world, pedido)
    new_turn(world)
    assert (await call(pedido, world.ctx, acao="finalizar")).is_error


async def _add_other_item(world, pedido):
    await add_item(world, pedido, name="Suco de Laranja")


async def _change_payment(world, pedido):
    await call(pedido, world.ctx, acao="definir_dados", forma_pagamento="cartao")


async def _remove_item(world, pedido):
    await call(pedido, world.ctx, acao="remover_item", item_id=world.items["Suco de Laranja"].id)


@pytest.mark.parametrize("change", [_add_other_item, _change_payment, _remove_item])
async def test_any_change_after_the_recap_requires_a_new_recap(world, pedido, change):
    await ready_order(world, pedido, troco_para=None)
    await call(pedido, world.ctx, acao="recapitular")
    new_turn(world)
    await change(world, pedido)

    stale = await call(pedido, world.ctx, acao="finalizar")
    assert stale.is_error
    assert order_of(world).status != "closed"

    assert (await confirm_and_finalize(world, pedido)).is_error is False


async def test_repeating_the_recap_with_nothing_changed_keeps_the_confirmation_valid(world, pedido):
    await ready_order(world, pedido)
    await call(pedido, world.ctx, acao="recapitular")
    new_turn(world)  # o Contact confirma e o modelo recapitula de novo antes de fechar
    await call(pedido, world.ctx, acao="recapitular")
    assert not (await call(pedido, world.ctx, acao="finalizar")).is_error


async def test_cash_change_edit_after_the_recap_requires_a_new_recap(world, pedido):
    await ready_order(world, pedido, troco_para=100)
    await call(pedido, world.ctx, acao="recapitular")
    new_turn(world)
    await call(pedido, world.ctx, acao="definir_dados", troco_para=200)
    assert (await call(pedido, world.ctx, acao="finalizar")).is_error


# ---------- adição idempotente no Turn ----------


async def test_adding_the_same_item_twice_in_one_turn_does_not_duplicate(world, pedido):
    await add_item(world, pedido, quantidade=2)
    result = await add_item(world, pedido, quantidade=2)
    assert not result.is_error
    lines = payload(result)["pedido"]["itens"]
    assert [(l["nome"], l["quantidade"]) for l in lines] == [("Pizza Toscana", 2)]
    assert payload(result)["pedido"]["subtotal"] == 90.0


async def test_same_item_with_another_note_in_the_same_turn_is_a_separate_line(world, pedido):
    await add_item(world, pedido, observacao="sem cebola")
    await add_item(world, pedido, observacao="bem passada")
    lines = payload(await call(pedido, world.ctx, acao="ver"))["pedido"]["itens"]
    assert sorted(l["observacao"] for l in lines) == ["bem passada", "sem cebola"]


async def test_adding_the_same_item_in_a_later_turn_adds_more(world, pedido):
    await add_item(world, pedido)
    new_turn(world)
    await add_item(world, pedido)
    assert payload(await call(pedido, world.ctx, acao="ver"))["pedido"]["itens"][0]["quantidade"] == 2


async def test_item_removed_and_added_again_in_the_same_turn_is_added(world, pedido):
    await add_item(world, pedido)
    await call(pedido, world.ctx, acao="remover_item", item_id=world.items["Pizza Toscana"].id)
    await add_item(world, pedido)
    assert payload(await call(pedido, world.ctx, acao="ver"))["pedido"]["itens"][0]["quantidade"] == 1


# ---------- Company fechada ----------


def at_utc(monkeypatch, *args):
    monkeypatch.setattr(checkout, "utc_now", lambda: datetime(*args, tzinfo=timezone.utc))


async def test_finalize_is_refused_when_the_company_is_closed_and_says_when_it_opens(world, pedido, monkeypatch):
    await ready_order(world, pedido)
    await call(pedido, world.ctx, acao="recapitular")
    new_turn(world)
    at_utc(monkeypatch, 2026, 10, 19, 13, 0)  # segunda 10:00 em Fortaleza; abre às 18:00
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error
    assert "hoje às 18:00" in payload(result)["erro"]
    assert order_of(world).status != "closed"

    at_utc(monkeypatch, 2026, 10, 19, 21, 0)  # 18:00 em Fortaleza: abriu, e o pedido segue montado
    assert not (await call(pedido, world.ctx, acao="finalizar")).is_error


async def test_closed_after_the_last_window_points_to_tomorrow(world, pedido, monkeypatch):
    await ready_order(world, pedido)
    await call(pedido, world.ctx, acao="recapitular")
    new_turn(world)
    at_utc(monkeypatch, 2026, 10, 20, 2, 30)  # segunda 23:30 em Fortaleza
    assert "amanhã às 18:00" in payload(await call(pedido, world.ctx, acao="finalizar"))["erro"]


async def test_company_without_business_hours_can_always_close(world, pedido, monkeypatch):
    world.company.business_hours = None
    world.db.commit()
    at_utc(monkeypatch, 2026, 10, 19, 13, 0)
    await ready_order(world, pedido)
    assert not (await confirm_and_finalize(world, pedido)).is_error
