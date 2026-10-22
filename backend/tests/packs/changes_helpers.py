"""Fixtures e helpers compartilhados pelos testes de cancelar/alterar (#33)."""

from datetime import datetime, timezone

from pack_helpers import (
    add_item,
    call,
    confirm_and_finalize,
    deliver_reply,
    fill_delivery,
    new_turn,
    order_of,
)

from app.models import PaymentRecord

OPEN_NOW = datetime(2026, 10, 19, 23, 0, tzinfo=timezone.utc)  # o `utc_now` fixado em tests/packs/conftest.py
IN_PREPARATION_OR_LATER = ["in_production", "sent", "delivered"]


async def closed_order(world, pedido, payment="dinheiro"):
    """Order confirmado e fechado: 2 Pizza Toscana (90) + taxa 5 = 95."""
    await add_item(world, pedido, quantidade=2)
    await fill_delivery(world, pedido, forma_pagamento=payment)
    result = await confirm_and_finalize(world, pedido)
    assert not result.is_error, result.content
    new_turn(world)  # o Contact escreve de novo depois da confirmação
    return order_of(world)


async def reconfirm(world, pedido):
    """Recapitula a alteração, a resposta chega ao Contact e ele confirma num Turn seguinte."""
    assert not (await call(pedido, world.ctx, acao="recapitular")).is_error
    deliver_reply(world)
    new_turn(world)
    return await call(pedido, world.ctx, acao="finalizar")


def pix_records(world):
    world.db.expire_all()
    return world.db.query(PaymentRecord).order_by(PaymentRecord.created_at, PaymentRecord.id).all()


def valid_pix(world):
    return [r for r in pix_records(world) if r.status in ("pending", "paid")]


def set_status(world, status):
    order = order_of(world)
    order.status = status
    world.db.commit()
