"""Estornos Pix pendentes (#33): Pix invalidado por cancelamento ou alteração do Order, para a Company estornar à mão.

Escopo pelas Instances do usuário (`instance_ids_for_user`); fora dele a resposta é 404.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.access import instance_ids_for_user
from app.api.deps import get_current_user, get_db
from app.models import CustomerOrder, PaymentRecord, User

router = APIRouter()


def _pending_refunds(db: Session, user: User):
    query = (
        db.query(PaymentRecord, CustomerOrder)
        .join(CustomerOrder, CustomerOrder.id == PaymentRecord.order_id)
        .filter(PaymentRecord.refund_status == "pending")
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
    rows = _pending_refunds(db, current_user).order_by(PaymentRecord.refund_flagged_at, PaymentRecord.id).all()
    return {"refunds": [_row(record, order) for record, order in rows]}


@router.post("/refunds/{record_id}/refunded")
def mark_refunded(record_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    found = _pending_refunds(db, current_user).filter(PaymentRecord.id == record_id).first()
    if not found:
        raise HTTPException(status_code=404, detail="Estorno pendente não encontrado")
    record, order = found
    record.refund_status = "refunded"
    record.refunded_at = datetime.now(timezone.utc)
    db.commit()
    return _row(record, order)
