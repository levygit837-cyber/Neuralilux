"""Cancelar e alterar o Order já confirmado, enquanto ainda não entrou em preparo (#33).

Só o status `closed` (recebido, aguardando preparo) aceita as duas ações. Depois disso (`in_production`,
`sent`, `delivered`) o erro manda o Agent oferecer Handoff com o motivo. Alterar reabre o Order para a
montagem (`ready_for_confirmation`) e zera a Recap: o fechamento volta a passar por `recapitular` e pela
confirmação do Contact em Message posterior, o mesmo caminho do Order novo (`recap.py`). `closed_at` é
mantido na reabertura e é o que distingue o Order reaberto de um Order novo em montagem.
"""

from __future__ import annotations

from typing import Any

from app.agent.clock import utc_now
from app.agent.contracts import ToolContext
from app.models import CustomerOrder
from app.packs.catalog_orders import pix
from app.packs.catalog_orders.order_state import ACTIVE_STATUSES, STATUS_LABELS, active_order, view
from app.packs.catalog_orders.totals import brl
from app.packs.catalog_orders.validation import OrderError

CHANGEABLE = "closed"
_PAST_PREPARATION = ("in_production", "sent", "delivered")
_FINISHED = ("closed", "cancelled", *_PAST_PREPARATION)


def is_reopened(order: CustomerOrder) -> bool:
    """Order confirmado que voltou à montagem por uma alteração e ainda não foi reconfirmado."""
    return order.status in ACTIVE_STATUSES and order.closed_at is not None


def _confirmed_order(ctx: ToolContext) -> CustomerOrder | None:
    """O Order que cancelar/alterar mira: o reaberto, senão o mais recente já confirmado da Conversation."""
    current = active_order(ctx)
    if current is not None and is_reopened(current):
        return current
    return (
        ctx.db.query(CustomerOrder)
        .filter(CustomerOrder.conversation_id == ctx.conversation_id, CustomerOrder.status.in_(_FINISHED))
        .order_by(CustomerOrder.created_at.desc(), CustomerOrder.opened_at.desc())
        .first()
    )


def _handoff_hint(order: CustomerOrder, verb: str) -> str:
    return (
        f"O pedido {order.order_number} já está {STATUS_LABELS[order.status]}: não dá mais para {verb} por aqui. "
        f"Ofereça falar com um atendente e, se o cliente aceitar, chame transferir_atendente com o motivo "
        f"(quer {verb} o pedido {order.order_number})."
    )


def _require_changeable(ctx: ToolContext, verb: str, *, allow_reopened: bool) -> CustomerOrder:
    order = _confirmed_order(ctx)
    if order is None:
        raise OrderError("Não há pedido confirmado para " + verb + ". Pedido em montagem não precisa disso: use remover_item.")
    if order.status == "cancelled":
        raise OrderError(f"O pedido {order.order_number} já foi cancelado.")
    if order.status in _PAST_PREPARATION:
        raise OrderError(_handoff_hint(order, verb))
    if is_reopened(order):
        if allow_reopened:
            return order
        raise OrderError(
            f"O pedido {order.order_number} já está em alteração. Faça as mudanças, chame recapitular e peça a confirmação."
        )
    return order


def _refund_note(records: list) -> str:
    amounts = ", ".join(brl(r.amount) for r in records)
    return (
        f" O Pix de {amounts} foi invalidado e ficou registrado para estorno manual pela empresa: se o cliente "
        "já pagou, diga que a empresa cuida do estorno. Não prometa prazo."
    )


def cancelar_pedido(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    order = _require_changeable(ctx, "cancelar", allow_reopened=True)
    records = pix.invalidate_records(ctx.db, order, "cancelled")
    order.status = "cancelled"
    order.cancelled_at = utc_now()
    order.cancel_reason = " ".join(str(args.get("motivo") or "").split()) or None
    ctx.db.commit()
    message = f"Pedido {order.order_number} cancelado. Confirme o cancelamento ao cliente; não é preciso transferir."
    return {"pedido": view(order), "mensagem": message + (_refund_note(records) if records else "")}


def alterar_pedido(ctx: ToolContext, _args: dict[str, Any]) -> dict[str, Any]:
    order = _require_changeable(ctx, "alterar", allow_reopened=False)
    other = active_order(ctx)
    if other is not None and other.id != order.id:
        raise OrderError(
            "O cliente tem outro pedido em montagem. Termine ou esvazie esse antes de alterar o pedido já confirmado."
        )
    pix.invalidate_records(ctx.db, order, "superseded")
    order.status = "ready_for_confirmation"
    order.recap_signature = None
    order.recap_turn_id = None
    order.recap_delivered_at = None
    ctx.db.commit()
    return {
        "pedido": view(order),
        "mensagem": "Pedido reaberto para alteração. Aplique o que o cliente pediu (adicionar_item, remover_item, "
        "definir_dados), chame recapitular, mostre o pedido com o novo total e peça a confirmação. Só chame finalizar "
        "quando ele confirmar numa mensagem seguinte. Se havia Pix, o código antigo não vale mais: um novo sai no "
        "finalizar.",
    }
