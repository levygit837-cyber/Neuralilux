"""Status do Order pela Company (#34): máquina de transições e aviso ao Contact.

`closed` (recebido) → `in_production` (em preparo) → `sent` (saiu para entrega) → `delivered` (entregue), e a
Company ainda cancela um Order `closed` ou `in_production`. Qualquer outra mudança é recusada, inclusive mexer
num Order reaberto para alteração pelo Contact (`is_reopened`): ele só volta a andar depois de reconfirmado.

O cancelamento reaproveita `changes.cancel_order` (o mesmo do Contact), então o Pix invalidado entra na lista de
estornos. O aviso ao Contact sai pelo `sender` (envia e grava a Message `from_me` na Conversation). Falha no envio
não desfaz a mudança de status: é registrada em log e devolvida em `notification`.
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.models import CustomerOrder
from app.packs.catalog_orders.changes import OrderChanged, cancel_order, claim_status
from app.packs.catalog_orders.order_state import REOPENED_LABEL, STATUS_LABELS, is_reopened
from app.whatsapp.sender import send_and_persist

logger = structlog.get_logger()

TRANSITIONS: dict[str, tuple[str, ...]] = {
    "closed": ("in_production", "cancelled"),
    "in_production": ("sent", "cancelled"),
    "sent": ("delivered",),
}
# Estados que o painel lista como ativos (o reaberto para alteração também: mantém `closed_at`) e como finalizados.
ACTIVE_PANEL_STATUSES = ("closed", "in_production", "sent")
DONE_PANEL_STATUSES = ("delivered", "cancelled")
NOTIFICATION_FAILED = "Não foi possível avisar o cliente pelo WhatsApp. O status foi atualizado."


class TransitionError(Exception):
    """A mudança de status pedida não é permitida para o Order."""


def allowed_transitions(order: CustomerOrder) -> list[str]:
    if is_reopened(order):
        return []
    return list(TRANSITIONS.get(order.status, ()))


def status_label(order: CustomerOrder) -> str:
    return REOPENED_LABEL if is_reopened(order) else STATUS_LABELS.get(order.status, order.status)


def _contact_message(order: CustomerOrder, target: str, refunds: list) -> str:
    number = order.order_number
    if target == "in_production":
        return f"Seu pedido {number} está em preparo. Avisamos quando sair para entrega."
    if target == "sent":
        return f"Seu pedido {number} saiu para entrega."
    if target == "delivered":
        return f"Seu pedido {number} foi entregue. Bom apetite!"
    text = f"Seu pedido {number} foi cancelado pela empresa."
    if refunds:
        text += " A empresa vai conferir o Pix e fazer o estorno se o pagamento foi feito."
    return text


async def _notify(db: Session, order: CustomerOrder, text: str) -> dict[str, Any]:
    try:
        await send_and_persist(db, order.instance, order.conversation, order.contact, text, sent_by="system")
    except Exception:
        db.rollback()  # o status já foi gravado; só descarta o que o envio deixou pela metade
        logger.exception("Failed to notify the Contact about the Order status", order_id=order.id, status=order.status)
        return {"sent": False, "error": NOTIFICATION_FAILED}
    return {"sent": True, "error": None}


async def change_status(db: Session, order: CustomerOrder, target: str) -> dict[str, Any]:
    """Move o Order para `target` e avisa o Contact; devolve o resultado do aviso. `TransitionError` se não for permitida."""
    if is_reopened(order):
        raise TransitionError(
            f"O pedido {order.order_number} está em alteração pelo cliente: só dá para mudar o status depois "
            "que ele reconfirmar."
        )
    if target not in TRANSITIONS.get(order.status, ()):
        raise TransitionError(
            f"Não dá para mudar o pedido {order.order_number} de \"{STATUS_LABELS.get(order.status, order.status)}\" "
            f"para \"{STATUS_LABELS.get(target, target)}\"."
        )
    refunds: list = []
    try:
        if target == "cancelled":
            refunds = cancel_order(db, order, None)
        else:
            claim_status(db, order, status=target)
        db.commit()
    except OrderChanged as exc:
        db.rollback()  # perdeu a corrida: nada foi gravado e o Contact não é avisado
        raise TransitionError(str(exc)) from exc
    return await _notify(db, order, _contact_message(order, target, refunds))

