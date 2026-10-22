"""Fechamento confiável do Order (#32): recapitulação entregue, adição idempotente e Company fechada."""

from datetime import datetime, timedelta, timezone

import pytest
from pack_helpers import (
    DELIVERED_AT,
    add_item,
    call,
    confirm_and_finalize,
    deliver_reply,
    fill_delivery,
    make_world,
    new_turn,
    order_of,
    payload,
    tool_named,
)

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


async def recap_delivered(world, pedido):
    """Recapitula, a resposta chega ao Contact e ele escreve outra Message (Turn novo)."""
    assert not (await call(pedido, world.ctx, acao="recapitular")).is_error
    deliver_reply(world)
    new_turn(world)


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


async def test_recap_whose_reply_never_reached_the_contact_does_not_allow_finalize(world, pedido):
    await ready_order(world, pedido)
    await call(pedido, world.ctx, acao="recapitular")
    new_turn(world)  # a resposta com a recapitulação falhou/foi descartada: nenhuma entrega
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error
    assert order_of(world).status != "closed"


async def test_delivery_of_another_turns_reply_does_not_validate_the_recap(world, pedido):
    await ready_order(world, pedido)
    await call(pedido, world.ctx, acao="recapitular")
    CatalogOrdersPack().on_reply_delivered(world.db, world.conversation, "outro-turn", DELIVERED_AT)
    new_turn(world)
    assert (await call(pedido, world.ctx, acao="finalizar")).is_error


async def test_finalize_after_a_delivered_recap_in_a_previous_turn_closes_the_order(world, pedido):
    await ready_order(world, pedido)
    result = await confirm_and_finalize(world, pedido)
    assert not result.is_error
    assert payload(result)["pedido"]["status"] == "closed"
    assert order_of(world).status == "closed"


async def test_confirmation_typed_before_the_recap_was_delivered_does_not_close(world, pedido):
    await ready_order(world, pedido)
    await call(pedido, world.ctx, acao="recapitular")
    deliver_reply(world, at=DELIVERED_AT)
    for trigger in (DELIVERED_AT - timedelta(minutes=1), DELIVERED_AT):
        new_turn(world, trigger_at=trigger)
        result = await call(pedido, world.ctx, acao="finalizar")
        assert result.is_error
        assert order_of(world).status != "closed"

    new_turn(world, trigger_at=DELIVERED_AT + timedelta(seconds=1))
    assert not (await call(pedido, world.ctx, acao="finalizar")).is_error


async def test_recap_returns_the_order_with_the_real_total(world, pedido):
    await ready_order(world, pedido)
    data = payload(await call(pedido, world.ctx, acao="recapitular"))
    assert data["pedido"]["total"] == 59.5  # 45 + 9.50 dos itens + 5 de taxa


async def test_recap_of_an_incomplete_order_is_refused_and_does_not_unlock_finalize(world, pedido):
    await add_item(world, pedido)
    result = await call(pedido, world.ctx, acao="recapitular")
    assert result.is_error and "nome" in payload(result)["erro"]
    await fill_delivery(world, pedido)
    deliver_reply(world)
    new_turn(world)
    assert (await call(pedido, world.ctx, acao="finalizar")).is_error


async def _add_other_item(world, pedido):
    await add_item(world, pedido, name="Refrigerante Cola 2L")


async def _more_of_the_same_item(world, pedido):
    await add_item(world, pedido, name="Suco de Laranja")  # a linha existente passa de 1 para 2


async def _add_a_note(world, pedido):
    await add_item(world, pedido, name="Suco de Laranja", observacao="sem gelo")


async def _change_payment(world, pedido):
    await call(pedido, world.ctx, acao="definir_dados", forma_pagamento="cartao")


async def _change_name(world, pedido):
    await call(pedido, world.ctx, acao="definir_dados", nome="Joana Lima")


async def _change_address(world, pedido):
    await call(pedido, world.ctx, acao="definir_dados", endereco="Rua B 45, Aldeota")


async def _remove_item(world, pedido):
    await call(pedido, world.ctx, acao="remover_item", item_id=world.items["Suco de Laranja"].id)


async def _remove_one_unit(world, pedido):
    await call(pedido, world.ctx, acao="remover_item", item_id=world.items["Pizza Toscana"].id, quantidade=1)


@pytest.mark.parametrize(
    "change",
    [
        _add_other_item,
        _more_of_the_same_item,
        _add_a_note,
        _change_payment,
        _change_name,
        _change_address,
        _remove_item,
        _remove_one_unit,
    ],
)
async def test_any_change_after_the_recap_requires_a_new_recap(world, pedido, change):
    await add_item(world, pedido, quantidade=2)  # remover 1 unidade deixa a linha com 1
    await add_item(world, pedido, name="Suco de Laranja")
    await fill_delivery(world, pedido, troco_para=None)
    await recap_delivered(world, pedido)
    await change(world, pedido)

    stale = await call(pedido, world.ctx, acao="finalizar")
    assert stale.is_error
    assert order_of(world).status != "closed"

    assert (await confirm_and_finalize(world, pedido)).is_error is False


async def test_repeating_the_recap_with_nothing_changed_keeps_the_confirmation_valid(world, pedido):
    await ready_order(world, pedido)
    await recap_delivered(world, pedido)
    await call(pedido, world.ctx, acao="recapitular")  # o Contact confirma e o modelo recapitula de novo antes de fechar
    assert not (await call(pedido, world.ctx, acao="finalizar")).is_error


async def test_cash_change_edit_after_the_recap_requires_a_new_recap(world, pedido):
    await ready_order(world, pedido, troco_para=100)
    await recap_delivered(world, pedido)
    await call(pedido, world.ctx, acao="definir_dados", troco_para=200)
    assert (await call(pedido, world.ctx, acao="finalizar")).is_error


async def test_a_resumed_order_needs_its_own_recap(world, pedido):
    await ready_order(world, pedido)
    await recap_delivered(world, pedido)
    CatalogOrdersPack().on_session_start(world.db, world.conversation)  # Session nova: o Order vira abandonado
    world.db.commit()
    new_turn(world)

    assert not (await call(pedido, world.ctx, acao="retomar_pedido")).is_error
    await fill_delivery(world, pedido)
    new_turn(world)
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error and "recapitular" in payload(result)["erro"]

    assert not (await confirm_and_finalize(world, pedido)).is_error


# ---------- adição idempotente no Turn ----------


async def test_adding_the_same_item_twice_in_one_turn_does_not_duplicate(world, pedido):
    await add_item(world, pedido, quantidade=2)
    result = await add_item(world, pedido, quantidade=2)
    assert not result.is_error
    lines = payload(result)["pedido"]["itens"]
    assert [(l["nome"], l["quantidade"]) for l in lines] == [("Pizza Toscana", 2)]
    assert payload(result)["pedido"]["subtotal"] == 90.0


async def test_adding_the_same_item_with_another_quantity_in_one_turn_is_added(world, pedido):
    await add_item(world, pedido, quantidade=1)
    await add_item(world, pedido, quantidade=2)
    lines = payload(await call(pedido, world.ctx, acao="ver"))["pedido"]["itens"]
    assert [(l["nome"], l["quantidade"]) for l in lines] == [("Pizza Toscana", 3)]


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
    await recap_delivered(world, pedido)
    at_utc(monkeypatch, 2026, 10, 19, 13, 0)  # segunda 10:00 em Fortaleza; abre às 18:00
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error
    assert "hoje às 18:00" in payload(result)["erro"]
    assert order_of(world).status != "closed"

    at_utc(monkeypatch, 2026, 10, 19, 21, 0)  # 18:00 em Fortaleza: abriu, e o pedido segue montado
    assert not (await call(pedido, world.ctx, acao="finalizar")).is_error


async def test_closed_after_the_last_window_points_to_tomorrow(world, pedido, monkeypatch):
    await ready_order(world, pedido)
    await recap_delivered(world, pedido)
    at_utc(monkeypatch, 2026, 10, 20, 2, 30)  # segunda 23:30 em Fortaleza
    assert "amanhã às 18:00" in payload(await call(pedido, world.ctx, acao="finalizar"))["erro"]


async def test_window_crossing_midnight_is_open_after_midnight_and_closed_at_dawn(world, pedido, monkeypatch):
    world.company.business_hours = {day: [["18:00", "02:00"]] for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    world.db.commit()
    await ready_order(world, pedido)
    await recap_delivered(world, pedido)

    at_utc(monkeypatch, 2026, 10, 20, 4, 0)  # terça 01:00 em Fortaleza: ainda é o expediente de segunda
    assert not (await call(pedido, world.ctx, acao="finalizar")).is_error


async def test_window_crossing_midnight_refuses_at_dawn_and_says_when_it_opens(world, pedido, monkeypatch):
    world.company.business_hours = {day: [["18:00", "02:00"]] for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    world.db.commit()
    await ready_order(world, pedido)
    await recap_delivered(world, pedido)

    at_utc(monkeypatch, 2026, 10, 20, 6, 0)  # terça 03:00 em Fortaleza: fechou às 02:00
    result = await call(pedido, world.ctx, acao="finalizar")
    assert result.is_error
    assert "hoje às 18:00" in payload(result)["erro"]
    assert order_of(world).status != "closed"


async def test_company_without_business_hours_can_always_close(world, pedido, monkeypatch):
    world.company.business_hours = None
    world.db.commit()
    at_utc(monkeypatch, 2026, 10, 19, 13, 0)
    await ready_order(world, pedido)
    assert not (await confirm_and_finalize(world, pedido)).is_error
