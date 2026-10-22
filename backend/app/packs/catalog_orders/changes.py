"""Cancelar e alterar o Order já confirmado, enquanto ainda não entrou em preparo (#33).

Só o status `closed` (recebido, aguardando preparo) aceita as duas ações. Depois disso (`in_production`,
`sent`, `delivered`) o erro manda o Agent oferecer Handoff com o motivo. Alterar reabre o Order para a
montagem (`ready_for_confirmation`) e zera a Recap: o fechamento volta a passar por `recapitular` e pela
confirmação do Contact em Message posterior, o mesmo caminho do Order novo (`recap.py`).

Alterar guarda o estado confirmado em `Order.confirmed_snapshot` (itens, dados, totais e Pix válidos). Se a
Session acaba sem a alteração ser reconfirmada, `restore_confirmed` devolve o Order a esse estado: o pedido
que o Contact confirmou nunca se perde nem vira `abandoned`. `closed_at` é mantido na reabertura e distingue
o Order reaberto de um Order novo em montagem (`order_state.is_reopened`).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.agent.clock import as_utc, utc_now
from app.agent.contracts import ToolContext
from app.models import Conversation, CustomerOrder, CustomerOrderItem
from app.packs.catalog_orders import pix
from app.packs.catalog_orders.order_state import ACTIVE_STATUSES, STATUS_LABELS, active_order, is_reopened, view
from app.packs.catalog_orders.recap import set_recap
from app.packs.catalog_orders.totals import brl
from app.packs.catalog_orders.validation import OrderError

_PAST_PREPARATION = ("in_production", "sent", "delivered")
_FINISHED = ("closed", "cancelled", *_PAST_PREPARATION)
_ORDER_FIELDS = ("customer_name", "customer_address", "delivery_type", "payment_method")
_MONEY_FIELDS = ("change_for", "delivery_fee", "total_amount")
_ITEM_FIELDS = ("menu_item_id", "item_name", "quantity", "unit_price", "subtotal_price", "notes", "sort_order")


def _snapshot(order: CustomerOrder, records: list) -> dict[str, Any]:
    return {
        "closed_at": order.closed_at.isoformat(),
        **{f: getattr(order, f) for f in _ORDER_FIELDS},
        **{f: None if getattr(order, f) is None else str(getattr(order, f)) for f in _MONEY_FIELDS},
        "items": [
            {f: str(getattr(line, f)) if isinstance(getattr(line, f), Decimal) else getattr(line, f) for f in _ITEM_FIELDS}
            for line in order.items
        ],
        "pix": [{"id": r.id, "status": r.status} for r in records],
    }


def restore_confirmed(db: Session, order: CustomerOrder) -> bool:
    """Devolve o Order reaberto ao estado confirmado (`closed`), com os Pix de antes de volta a valer.

    Chamado quando a Session acaba sem a alteração ser reconfirmada. Sem `commit`. Sem snapshot (não deveria
    ocorrer) devolve False e o Order continua reaberto, nunca abandonado.
    """
    snap = order.confirmed_snapshot
    if not snap:
        return False
    for field in _ORDER_FIELDS:
        setattr(order, field, snap[field])
    for field in _MONEY_FIELDS:
        setattr(order, field, None if snap[field] is None else Decimal(snap[field]))
    order.items[:] = [
        CustomerOrderItem(**{f: Decimal(v) if f in ("unit_price", "subtotal_price") else v for f, v in item.items()})
        for item in snap["items"]
    ]
    order.status = "closed"
    order.closed_at = datetime.fromisoformat(snap["closed_at"])
    set_recap(order, None, None)
    order.confirmed_snapshot = None
    for entry in snap["pix"]:
        pix.revive_record(db, entry["id"], entry["status"])
    db.flush()
    return True


def _target(ctx: ToolContext, number: str | None) -> CustomerOrder | None:
    """O Order que cancelar/alterar mira: o `number` pedido, o reaberto ou o mais recente já confirmado."""
    query = ctx.db.query(CustomerOrder).filter(CustomerOrder.conversation_id == ctx.conversation_id)
    if number:
        return query.filter(CustomerOrder.order_number == number).first()
    current = active_order(ctx)
    if current is not None and is_reopened(current):
        return current
    return (
        query.filter(CustomerOrder.status.in_(_FINISHED))
        .order_by(CustomerOrder.created_at.desc(), CustomerOrder.opened_at.desc())
        .first()
    )


def _in_recent_sessions(ctx: ToolContext, order: CustomerOrder) -> bool:
    """O Order foi confirmado na Session atual ou na anterior. Mais antigo que isso só um Attendant mexe."""
    conversation = ctx.db.get(Conversation, ctx.conversation_id)
    since = conversation.previous_session_started_at or conversation.session_started_at if conversation else None
    moment = order.closed_at or order.created_at
    return since is None or moment is None or as_utc(moment) >= as_utc(since)


def _handoff_hint(order: CustomerOrder, verb: str, reason: str) -> str:
    return (
        f"O pedido {order.order_number} {reason}: não dá mais para {verb} por aqui. "
        f"Ofereça falar com um atendente e, se o cliente aceitar, chame transferir_atendente com o motivo "
        f"(quer {verb} o pedido {order.order_number})."
    )


def _abandoned_error(order: CustomerOrder, verb: str) -> OrderError:
    return OrderError(
        f"O pedido {order.order_number} foi abandonado num atendimento anterior e não chegou a ser confirmado: "
        f"não há o que {verb}. Se o cliente quiser o mesmo pedido, use retomar_pedido."
    )


def _require_changeable(ctx: ToolContext, verb: str, number: str | None) -> CustomerOrder:
    # Import local: `session_orders` importa este módulo (restore_confirmed).
    from app.packs.catalog_orders.session_orders import pending_abandoned

    order = _target(ctx, number)
    if order is None:
        abandoned = pending_abandoned(ctx)
        if abandoned is not None and not number:
            raise _abandoned_error(abandoned, verb)
        raise OrderError(
            f"Não há pedido confirmado para {verb}"
            + (f" com o número {number}" if number else "")
            + ". Pedido em montagem não precisa disso: use remover_item."
        )
    if order.status == "cancelled":
        raise OrderError(f"O pedido {order.order_number} já foi cancelado.")
    if order.status == "abandoned":
        raise _abandoned_error(order, verb)
    if order.status in _PAST_PREPARATION:
        raise OrderError(_handoff_hint(order, verb, f"já está {STATUS_LABELS[order.status]}"))
    if order.status in ACTIVE_STATUSES and not is_reopened(order):
        raise OrderError(f"O pedido {order.order_number} ainda está em montagem: não há o que {verb}. Use remover_item.")
    if not _in_recent_sessions(ctx, order):
        raise OrderError(_handoff_hint(order, verb, "é de um atendimento anterior"))
    return order


def _refund_note(records: list) -> str:
    amounts = ", ".join(brl(r.amount) for r in records)
    return (
        f" O Pix de {amounts} foi invalidado e a empresa confere se houve pagamento e estorna à mão: se o cliente "
        "já pagou, diga que a empresa cuida do estorno. Não prometa prazo."
    )


def cancelar_pedido(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    number = str(args.get("numero") or "").strip() or None
    order = _require_changeable(ctx, "cancelar", number)
    other = active_order(ctx)
    if other is not None and other.id != order.id and not number:
        raise OrderError(
            f"O cliente tem um pedido em montagem e o pedido {order.order_number} já confirmado. Pergunte qual dos dois "
            f"ele quer cancelar. Para cancelar o confirmado, chame cancelar_pedido com numero={order.order_number}; "
            "o que está em montagem se esvazia com remover_item."
        )
    records = pix.invalidate_records(ctx.db, order, "cancelled")
    order.status = "cancelled"
    order.cancelled_at = utc_now()
    order.cancel_reason = " ".join(str(args.get("motivo") or "").split()) or None
    order.confirmed_snapshot = None
    ctx.db.commit()
    message = f"Pedido {order.order_number} cancelado. Confirme o cancelamento ao cliente; não é preciso transferir."
    return {"pedido": view(order), "mensagem": message + (_refund_note(records) if records else "")}


def alterar_pedido(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    order = _require_changeable(ctx, "alterar", str(args.get("numero") or "").strip() or None)
    if is_reopened(order):
        raise OrderError(
            f"O pedido {order.order_number} já está em alteração. Faça as mudanças, chame recapitular e peça a confirmação."
        )
    other = active_order(ctx)
    if other is not None and other.id != order.id:
        raise OrderError(
            "O cliente tem outro pedido em montagem. Termine ou esvazie esse antes de alterar o pedido já confirmado."
        )
    if order.closed_at is None:  # `closed_at` é o que marca o Order como reaberto; Order antigo sem ele o ganha aqui
        order.closed_at = utc_now()
    order.confirmed_snapshot = _snapshot(order, pix.valid_records(ctx.db, order))
    pix.invalidate_records(ctx.db, order, "superseded")
    order.status = "ready_for_confirmation"
    set_recap(order, None, None)
    ctx.db.commit()
    return {
        "pedido": view(order),
        "mensagem": "Pedido reaberto para alteração. Aplique o que o cliente pediu (adicionar_item, remover_item, "
        "definir_dados), chame recapitular, mostre o pedido com o novo total e peça a confirmação. Só chame finalizar "
        "quando ele confirmar numa mensagem seguinte. Se havia Pix, o código antigo não vale mais: um novo sai no "
        "finalizar.",
    }
