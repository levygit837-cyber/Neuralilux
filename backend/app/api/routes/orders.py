"""Orders da Company (#34) e estornos Pix (#33).

Painel: a Company lista os Orders confirmados e move o status (`services/order_status.py`); o Contact é avisado
no WhatsApp a cada mudança. Estornos: Pix invalidado por cancelamento ou alteração do Order, para a Company
estornar à mão. `refund_status`: `pending` (o Pix estava pago: devolver), `verify` (estava pendente, mas o Contact
pode ter pago: conferir no banco), `refunded` (devolvido) e `dismissed` (conferido, nada a devolver). As baixas
são idempotentes.

Escopo pelas Instances do usuário (`instance_ids_for_user`); Order ou estorno fora dele é 404.
"""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, selectinload

from app.api.access import instance_ids_for_user
from app.api.deps import get_current_user, get_db
from app.models import CustomerOrder, PaymentRecord, User
from app.packs.catalog_orders.order_state import ACTIVE_STATUSES, is_reopened
from app.services.order_status import PANEL_STATUSES, TransitionError, allowed_transitions, change_status, status_label

router = APIRouter()


OPEN_REFUNDS = ("pending", "verify")


def _scoped_refunds(db: Session, user: User, statuses: tuple[str, ...]):
    query = (
        db.query(PaymentRecord, CustomerOrder)
        .join(CustomerOrder, CustomerOrder.id == PaymentRecord.order_id)
        .filter(PaymentRecord.refund_status.in_(statuses))
    )
    instance_ids = instance_ids_for_user(db, user)
    if instance_ids is not None:
        query = query.filter(CustomerOrder.instance_id.in_(instance_ids))
    return query


def _row(record: PaymentRecord, order: CustomerOrder) -> dict:
    return {
        "id": record.id,
        "order_id": order.id,
        "order_number": order.order_number,
        "order_status": order.status,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "amount": float(record.amount),
        "payment_status": record.status,
        "refund_status": record.refund_status,
        "refund_flagged_at": record.refund_flagged_at.isoformat() if record.refund_flagged_at else None,
    }


@router.get("/refunds")
def list_pending_refunds(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = _scoped_refunds(db, current_user, OPEN_REFUNDS).order_by(PaymentRecord.refund_flagged_at, PaymentRecord.id).all()
    return {"refunds": [_row(record, order) for record, order in rows]}


def _resolve(db: Session, user: User, record_id: str, final: str) -> dict:
    """Dá baixa no estorno. Repetir a baixa que já foi dada devolve o mesmo corpo; a baixa oposta é 409."""
    found = _scoped_refunds(db, user, (*OPEN_REFUNDS, "refunded", "dismissed")).filter(PaymentRecord.id == record_id).first()
    if not found:
        raise HTTPException(status_code=404, detail="Estorno não encontrado")
    record, order = found
    if record.refund_status in OPEN_REFUNDS:
        record.refund_status = final
        record.refunded_at = datetime.now(timezone.utc)
        db.commit()
    elif record.refund_status != final:
        raise HTTPException(status_code=409, detail=f"Este estorno já foi marcado como {record.refund_status}")
    return _row(record, order)


@router.post("/refunds/{record_id}/refunded")
def mark_refunded(record_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _resolve(db, current_user, record_id, "refunded")


@router.post("/refunds/{record_id}/dismissed")
def dismiss_refund(record_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _resolve(db, current_user, record_id, "dismissed")


# ---------- painel de Orders (#34) ----------


class StatusChange(BaseModel):
    status: Literal["in_production", "sent", "delivered", "cancelled"]


def _scoped_orders(db: Session, user: User):
    query = db.query(CustomerOrder).options(selectinload(CustomerOrder.items))
    instance_ids = instance_ids_for_user(db, user)
    if instance_ids is not None:
        query = query.filter(CustomerOrder.instance_id.in_(instance_ids))
    return query


def _refund_status(db: Session, order: CustomerOrder) -> str | None:
    """O estorno mais recente do Order (qualquer fase), ou None se nenhum Pix foi invalidado."""
    record = (
        db.query(PaymentRecord)
        .filter(PaymentRecord.order_id == order.id, PaymentRecord.refund_status.isnot(None))
        .order_by(PaymentRecord.refund_flagged_at.desc(), PaymentRecord.id)
        .first()
    )
    return record.refund_status if record else None


def _panel_row(db: Session, order: CustomerOrder) -> dict:
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "status_label": status_label(order),
        "being_altered": is_reopened(order),
        "allowed_transitions": allowed_transitions(order),
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "items": [
            {"name": line.item_name, "quantity": line.quantity, "subtotal": float(line.subtotal_price)}
            for line in order.items
        ],
        "total_amount": float(order.total_amount or 0),
        "payment_method": order.payment_method,
        "delivery_type": order.delivery_type,
        "refund_status": _refund_status(db, order),
        "opened_at": order.opened_at.isoformat() if order.opened_at else None,
    }


@router.get("")
def list_orders(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Orders confirmados da Company, do mais recente ao mais antigo; inclui os reabertos para alteração."""
    confirmed = or_(
        CustomerOrder.status.in_(PANEL_STATUSES),
        and_(CustomerOrder.status.in_(ACTIVE_STATUSES), CustomerOrder.closed_at.isnot(None)),
    )
    orders = _scoped_orders(db, current_user).filter(confirmed).order_by(CustomerOrder.opened_at.desc(), CustomerOrder.id).limit(limit).all()
    return {"orders": [_panel_row(db, order) for order in orders]}


@router.post("/{order_id}/status")
async def change_order_status(
    order_id: str,
    body: StatusChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move o Order na máquina de status e avisa o Contact. Falha no aviso não desfaz a mudança (`notification`)."""
    order = _scoped_orders(db, current_user).filter(CustomerOrder.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    try:
        notification = await change_status(db, order, body.status)
    except TransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"order": _panel_row(db, order), "notification": notification}
