"""Cancelar e alterar (#33) ao longo das Sessions: alcance, virada no meio da alteração e retomar."""

from datetime import timedelta
from decimal import Decimal

import pytest
from changes_helpers import (
    OPEN_NOW,
    closed_order,
    pix_records,
    reconfirm,
    valid_pix,
)
from pack_helpers import add_item, call, new_turn, order_of, payload

from app.models import CustomerOrder
from app.packs.catalog_orders.pack import CatalogOrdersPack

pytestmark = pytest.mark.asyncio


# ---------- só o Order da Session atual ou da anterior ----------


def set_sessions(world, previous, current):
    world.conversation.previous_session_started_at = previous
    world.conversation.session_started_at = current
    world.db.commit()


async def test_order_from_days_ago_is_not_changed_here_and_leads_to_handoff(world, pedido):
    order = await closed_order(world, pedido)
    set_sessions(world, previous=OPEN_NOW + timedelta(days=4), current=OPEN_NOW + timedelta(days=5))
    for action in ("cancelar_pedido", "alterar_pedido"):
        result = await call(pedido, world.ctx, acao=action)
        assert result.is_error and "atendimento anterior" in payload(result)["erro"]
        assert "transferir_atendente" in payload(result)["erro"]
    assert order_of(world).status == "closed" and order_of(world).id == order.id


async def test_order_confirmed_in_the_previous_session_can_still_be_cancelled(world, pedido):
    await closed_order(world, pedido)
    set_sessions(world, previous=OPEN_NOW - timedelta(hours=1), current=OPEN_NOW + timedelta(hours=5))

    assert not (await call(pedido, world.ctx, acao="cancelar_pedido")).is_error
    assert order_of(world).status == "cancelled"


# ---------- Session que acaba no meio da alteração ----------


async def rollover(world):
    CatalogOrdersPack().on_session_start(world.db, world.conversation)
    world.db.commit()


async def test_session_rollover_during_an_alteration_restores_the_confirmed_order(world, pedido):
    original = await closed_order(world, pedido, payment="pix")
    (old,) = pix_records(world)
    old_id, old_txid = old.id, old.txid
    await call(pedido, world.ctx, acao="alterar_pedido")
    await add_item(world, pedido, name="Refrigerante Cola 2L")
    await call(pedido, world.ctx, acao="definir_dados", tipo_entrega="retirada", forma_pagamento="dinheiro")
    assert order_of(world).total_amount == Decimal("102.00")

    await rollover(world)  # o Contact sumiu e voltou depois do limite da Session

    order = order_of(world)
    assert order.status == "closed"  # nunca abandoned
    assert order.id == original.id and order.confirmed_snapshot is None
    assert [(l.item_name, l.quantity) for l in order.items] == [("Pizza Toscana", 2)]
    assert (order.total_amount, order.delivery_fee) == (Decimal("95.00"), Decimal("5.00"))
    assert (order.delivery_type, order.payment_method, order.customer_name) == ("entrega", "pix", "Maria Silva")
    assert order.recap_signature is None
    # Pix coerente com o estado confirmado: exatamente um válido, o original, com o total do Order
    (valid,) = valid_pix(world)
    assert valid.id == old_id and valid.txid == old_txid and valid.status == "pending"
    assert valid.amount == order.total_amount
    assert valid.refund_status is None and valid.refund_flagged_at is None
    assert len(pix_records(world)) == 1


async def test_restored_order_can_be_altered_again_and_gets_a_new_distinct_pix(world, pedido):
    await closed_order(world, pedido, payment="pix")
    await call(pedido, world.ctx, acao="alterar_pedido")
    await rollover(world)

    assert not (await call(pedido, world.ctx, acao="alterar_pedido")).is_error
    await add_item(world, pedido, name="Suco de Laranja")
    assert not (await reconfirm(world, pedido)).is_error

    (current,) = valid_pix(world)
    assert current.amount == Decimal("104.50") and len(pix_records(world)) == 2
    assert len({r.txid for r in pix_records(world)}) == 2


async def test_session_rollover_still_abandons_a_plain_open_order_but_not_the_reopened_one(world, pedido):
    await closed_order(world, pedido)
    await call(pedido, world.ctx, acao="alterar_pedido")
    await rollover(world)
    assert order_of(world).status == "closed"

    await add_item(world, pedido, name="Suco de Laranja")  # pedido novo em montagem
    await rollover(world)
    world.db.expire_all()
    assert sorted(o.status for o in world.db.query(CustomerOrder).all()) == ["abandoned", "closed"]


async def test_reopened_order_without_snapshot_is_never_abandoned(world, pedido):
    await closed_order(world, pedido)
    await call(pedido, world.ctx, acao="alterar_pedido")
    order = order_of(world)
    order.confirmed_snapshot = None
    world.db.commit()

    await rollover(world)

    order = order_of(world)
    assert order.status == "ready_for_confirmation" and order.closed_at is not None
    assert payload(await call(pedido, world.ctx, acao="ver"))["pedido"]["em_alteracao"] is True


async def test_view_marks_the_reopened_order_as_being_altered(world, pedido):
    await closed_order(world, pedido)
    assert payload(await call(pedido, world.ctx, acao="ver")) == {"pedido": None, "mensagem": "Não há pedido em aberto."}
    await call(pedido, world.ctx, acao="alterar_pedido")

    view = payload(await call(pedido, world.ctx, acao="ver"))["pedido"]

    assert view["em_alteracao"] is True and "alteração" in view["status_descricao"]


# ---------- retomar depois de uma alteração ----------


async def test_resume_after_an_alteration_is_refused_while_the_order_is_being_altered(world, pedido):
    await closed_order(world, pedido)
    await call(pedido, world.ctx, acao="alterar_pedido")

    result = await call(pedido, world.ctx, acao="retomar_pedido")

    assert result.is_error  # há um pedido em alteração (ativo): nada a retomar nem a duplicar
    assert order_of(world).status == "ready_for_confirmation"


async def test_resume_after_cancelling_an_altered_order_has_nothing_to_resume(world, pedido):
    await closed_order(world, pedido)
    await call(pedido, world.ctx, acao="alterar_pedido")
    assert not (await call(pedido, world.ctx, acao="cancelar_pedido")).is_error
    await rollover(world)

    result = await call(pedido, world.ctx, acao="retomar_pedido")

    assert result.is_error and "Não há pedido abandonado" in payload(result)["erro"]


async def test_resume_works_for_a_plain_abandoned_order_even_with_a_restored_one_before(world, pedido):
    await closed_order(world, pedido)
    await call(pedido, world.ctx, acao="alterar_pedido")
    await rollover(world)  # restaurado, closed
    await add_item(world, pedido, name="Suco de Laranja", quantidade=2)
    await rollover(world)  # este sim abandoned
    new_turn(world)

    resumed = payload(await call(pedido, world.ctx, acao="retomar_pedido"))

    assert [i["nome"] for i in resumed["pedido"]["itens"]] == ["Suco de Laranja"]
