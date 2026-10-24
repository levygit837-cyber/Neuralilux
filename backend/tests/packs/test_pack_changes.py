"""Cancelar e alterar o Order antes do preparo (#33): transições permitidas e proibidas, Recap, Pix e txid."""

from decimal import Decimal

import pytest
from changes_helpers import (
    IN_PREPARATION_OR_LATER,
    closed_order,
    pix_records,
    reconfirm,
    set_status,
    valid_pix,
)
from pack_helpers import add_item, call, confirm_and_finalize, deliver_reply, fill_delivery, new_turn, order_of, payload

from app.models import Contact, Conversation, CustomerOrder, Ticket
from app.packs.catalog_orders.pack import CatalogOrdersPack

pytestmark = pytest.mark.asyncio


# ---------- cancelar ----------


async def test_cancel_right_after_confirming_cancels_without_handoff(world, pedido):
    await closed_order(world, pedido)

    result = await call(pedido, world.ctx, acao="cancelar_pedido", motivo="mudei de ideia")

    assert not result.is_error, result.content
    assert payload(result)["pedido"]["status"] == "cancelled"
    order = order_of(world)
    assert order.status == "cancelled"
    assert order.cancelled_at is not None and order.cancel_reason == "mudei de ideia"
    world.db.expire_all()
    assert world.db.query(Ticket).count() == 0
    assert world.db.get(Conversation, world.conversation.id).human_in_loop is False


@pytest.mark.parametrize("status", IN_PREPARATION_OR_LATER)
async def test_cancel_after_preparation_started_is_refused_and_points_to_handoff(world, pedido, status):
    await closed_order(world, pedido)
    set_status(world, status)

    result = await call(pedido, world.ctx, acao="cancelar_pedido")

    assert result.is_error
    assert "transferir_atendente" in payload(result)["erro"]
    assert order_of(world).status == status


async def test_cancel_of_an_already_cancelled_order_is_refused(world, pedido):
    await closed_order(world, pedido)
    assert not (await call(pedido, world.ctx, acao="cancelar_pedido")).is_error

    result = await call(pedido, world.ctx, acao="cancelar_pedido")

    assert result.is_error and "cancelado" in payload(result)["erro"]


async def test_cancel_without_any_order_is_refused(world, pedido):
    result = await call(pedido, world.ctx, acao="cancelar_pedido")
    assert result.is_error


async def test_cancel_never_touches_the_order_of_another_conversation(world, pedido):
    await closed_order(world, pedido)
    other_contact = Contact(
        instance_id=world.instance.id, phone_number="5511900000000", remote_jid="outra@s.whatsapp.net", name="Outra"
    )
    world.db.add(other_contact)
    world.db.flush()
    other = Conversation(
        instance_id=world.instance.id, contact_id=other_contact.id, remote_jid="outra@s.whatsapp.net"
    )
    world.db.add(other)
    world.db.commit()
    from dataclasses import replace

    other_ctx = replace(world.ctx, conversation_id=other.id)

    result = await call(pedido, other_ctx, acao="cancelar_pedido")

    assert result.is_error
    assert order_of(world).status == "closed"


async def test_cancel_with_pix_invalidates_the_record_and_flags_the_refund(world, pedido):
    await closed_order(world, pedido, payment="pix")

    result = await call(pedido, world.ctx, acao="cancelar_pedido")

    assert not result.is_error, result.content
    assert "estorno" in payload(result)["mensagem"].lower()
    (record,) = pix_records(world)
    assert record.status == "cancelled"
    # nada marca o Pix como pago: pendente vai para a lista "conferir", não para "devolver"
    assert record.refund_status == "verify" and record.refund_flagged_at is not None
    assert valid_pix(world) == []


async def test_cancel_of_a_paid_pix_flags_it_to_be_refunded(world, pedido):
    await closed_order(world, pedido, payment="pix")
    (record,) = pix_records(world)
    record.status = "paid"
    world.db.commit()

    assert not (await call(pedido, world.ctx, acao="cancelar_pedido")).is_error

    (record,) = pix_records(world)
    assert record.status == "cancelled" and record.refund_status == "pending"


async def test_cancel_without_pix_leaves_no_refund_flag(world, pedido):
    await closed_order(world, pedido, payment="dinheiro")
    await call(pedido, world.ctx, acao="cancelar_pedido")
    assert pix_records(world) == []


async def test_cancel_after_preparation_with_pix_does_not_touch_the_payment_record(world, pedido):
    await closed_order(world, pedido, payment="pix")
    set_status(world, "in_production")

    assert (await call(pedido, world.ctx, acao="cancelar_pedido")).is_error

    (record,) = pix_records(world)
    assert record.status == "pending" and record.refund_status is None


# ---------- alterar ----------


async def test_alter_reopens_the_order_and_requires_a_new_confirmed_recap(world, pedido):
    await closed_order(world, pedido)

    result = await call(pedido, world.ctx, acao="alterar_pedido")

    assert not result.is_error, result.content
    order = order_of(world)
    assert order.status == "ready_for_confirmation"
    assert order.recap_signature is None and order.recap_delivered_at is None
    # a confirmação antiga não vale: sem nova Recap, finalizar é recusado
    new_turn(world)
    refused = await call(pedido, world.ctx, acao="finalizar")
    assert refused.is_error and "recapitular" in payload(refused)["erro"]
    assert order_of(world).status == "ready_for_confirmation"


async def test_alter_adding_an_item_recomputes_the_total_and_asks_for_confirmation(world, pedido):
    await closed_order(world, pedido)
    await call(pedido, world.ctx, acao="alterar_pedido")

    added = payload(await add_item(world, pedido, name="Refrigerante Cola 2L"))
    assert added["pedido"]["total"] == 107.0  # 90 + 12 + 5 de taxa

    recap = payload(await call(pedido, world.ctx, acao="recapitular"))
    assert recap["pedido"]["total"] == 107.0
    deliver_reply(world)
    new_turn(world)
    closed = await call(pedido, world.ctx, acao="finalizar")

    assert not closed.is_error, closed.content
    order = order_of(world)
    assert order.status == "closed" and order.total_amount == Decimal("107.00")


async def test_alter_changing_the_address_recomputes_the_delivery_fee(world, pedido):
    await closed_order(world, pedido)
    await call(pedido, world.ctx, acao="alterar_pedido")

    data = payload(await call(pedido, world.ctx, acao="definir_dados", tipo_entrega="retirada"))

    assert data["pedido"]["taxa_entrega"] == 0.0 and data["pedido"]["total"] == 90.0


@pytest.mark.parametrize("status", IN_PREPARATION_OR_LATER)
async def test_alter_after_preparation_started_is_refused_and_points_to_handoff(world, pedido, status):
    await closed_order(world, pedido)
    set_status(world, status)

    result = await call(pedido, world.ctx, acao="alterar_pedido")

    assert result.is_error and "transferir_atendente" in payload(result)["erro"]
    order = order_of(world)
    assert order.status == status and order.recap_signature is not None


@pytest.mark.parametrize("status", ["cancelled", "abandoned"])
async def test_alter_of_a_cancelled_or_abandoned_order_is_refused(world, pedido, status):
    await closed_order(world, pedido)
    set_status(world, status)

    result = await call(pedido, world.ctx, acao="alterar_pedido")

    assert result.is_error
    assert order_of(world).status == status


async def test_alter_is_refused_while_another_order_is_being_built(world, pedido):
    await closed_order(world, pedido)
    await add_item(world, pedido, name="Suco de Laranja")  # pedido novo em montagem

    result = await call(pedido, world.ctx, acao="alterar_pedido")

    assert result.is_error
    world.db.expire_all()
    assert {o.status for o in world.db.query(CustomerOrder).all()} == {"closed", "open"}


async def test_alter_on_an_order_still_being_built_is_refused(world, pedido):
    await add_item(world, pedido)
    result = await call(pedido, world.ctx, acao="alterar_pedido")
    assert result.is_error


async def test_cancel_while_the_alteration_is_pending_cancels_the_order(world, pedido):
    await closed_order(world, pedido)
    await call(pedido, world.ctx, acao="alterar_pedido")

    result = await call(pedido, world.ctx, acao="cancelar_pedido")

    assert not result.is_error, result.content
    assert order_of(world).status == "cancelled"


# ---------- Pix ----------


async def test_alter_with_pix_supersedes_the_old_record_and_issues_a_new_one_with_the_new_amount(world, pedido):
    await closed_order(world, pedido, payment="pix")
    (old,) = pix_records(world)
    old_id, old_amount = old.id, old.amount
    assert old_amount == Decimal("95.00")

    await call(pedido, world.ctx, acao="alterar_pedido")
    # reaberto: o Pix antigo já não vale e ainda não existe outro
    assert valid_pix(world) == []
    (superseded,) = pix_records(world)
    assert superseded.id == old_id and superseded.status == "superseded"
    assert superseded.refund_status == "verify"

    await add_item(world, pedido, name="Refrigerante Cola 2L")
    closed = payload(await reconfirm(world, pedido))

    records = pix_records(world)
    assert len(records) == 2
    (current,) = valid_pix(world)
    assert current.id != old_id and current.amount == Decimal("107.00")
    assert closed["pix"]["valor"] == 107.0
    assert closed["pix"]["copia_e_cola"] == current.qr_code_data
    assert "107.00" in current.qr_code_data


async def test_repeated_alterations_never_leave_two_valid_pix_records(world, pedido):
    await closed_order(world, pedido, payment="pix")
    for name in ("Refrigerante Cola 2L", "Suco de Laranja"):
        await call(pedido, world.ctx, acao="alterar_pedido")
        await add_item(world, pedido, name=name)
        assert not (await reconfirm(world, pedido)).is_error
        new_turn(world)
        assert len(valid_pix(world)) == 1

    assert len(pix_records(world)) == 3
    assert valid_pix(world)[0].amount == order_of(world).total_amount


async def test_alter_that_moves_payment_from_pix_to_cash_leaves_no_valid_pix(world, pedido):
    await closed_order(world, pedido, payment="pix")
    await call(pedido, world.ctx, acao="alterar_pedido")
    await call(pedido, world.ctx, acao="definir_dados", forma_pagamento="dinheiro")

    result = await reconfirm(world, pedido)

    assert not result.is_error and "pix" not in payload(result)
    assert valid_pix(world) == []
    assert [r.status for r in pix_records(world)] == ["superseded"]


# ---------- txid distinto a cada Pix do Order ----------


async def test_regenerated_pix_has_a_distinct_valid_txid(world, pedido):
    first = payload(await closed_order_result(world, pedido))["pix"]["txid"]
    await call(pedido, world.ctx, acao="alterar_pedido")
    await add_item(world, pedido, name="Refrigerante Cola 2L")
    second = payload(await reconfirm(world, pedido))["pix"]["txid"]
    await call(pedido, world.ctx, acao="alterar_pedido")
    await add_item(world, pedido, name="Suco de Laranja")
    third = payload(await reconfirm(world, pedido))["pix"]["txid"]

    assert len({first, second, third}) == 3
    for txid in (first, second, third):
        assert txid.isalnum() and len(txid) <= 25
    by_txid = {r.txid: r for r in pix_records(world)}  # created_at empata no SQLite: não depende da ordem
    assert set(by_txid) == {first, second, third}
    # o txid do BR Code (campo 62, subcampo 05) é o mesmo gravado no registro
    assert f"05{len(second):02d}{second}" in by_txid[second].qr_code_data


async def closed_order_result(world, pedido):
    await add_item(world, pedido, quantidade=2)
    await fill_delivery(world, pedido, forma_pagamento="pix")
    result = await confirm_and_finalize(world, pedido)
    new_turn(world)
    return result


# ---------- cancelar com pedido em montagem ----------


async def test_cancel_refuses_to_pick_between_a_building_order_and_a_closed_one(world, pedido):
    await closed_order(world, pedido)
    await add_item(world, pedido, name="Suco de Laranja")  # pedido novo em montagem

    result = await call(pedido, world.ctx, acao="cancelar_pedido")

    assert result.is_error and "qual dos dois" in payload(result)["erro"]
    world.db.expire_all()
    assert {o.status for o in world.db.query(CustomerOrder).all()} == {"closed", "open"}


async def test_cancel_with_the_order_number_cancels_exactly_that_order(world, pedido):
    closed = await closed_order(world, pedido)
    await add_item(world, pedido, name="Suco de Laranja")

    result = await call(pedido, world.ctx, acao="cancelar_pedido", numero=closed.order_number)

    assert not result.is_error, result.content
    world.db.expire_all()
    statuses = {o.order_number: o.status for o in world.db.query(CustomerOrder).all()}
    assert statuses.pop(closed.order_number) == "cancelled" and list(statuses.values()) == ["open"]


async def test_cancel_of_a_building_order_is_refused(world, pedido):
    await add_item(world, pedido)
    result = await call(pedido, world.ctx, acao="cancelar_pedido")
    assert result.is_error and "remover_item" in payload(result)["erro"]


async def test_cancel_of_an_abandoned_order_is_refused_and_points_to_resume(world, pedido):
    await add_item(world, pedido)
    CatalogOrdersPack().on_session_start(world.db, world.conversation)
    world.db.commit()
    assert order_of(world).status == "abandoned"

    result = await call(pedido, world.ctx, acao="cancelar_pedido")

    assert result.is_error and "retomar_pedido" in payload(result)["erro"]
    assert order_of(world).status == "abandoned"
