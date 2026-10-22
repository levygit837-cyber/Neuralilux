"""Estornos Pix (#33): Pix invalidado por cancelamento ou alteração do Order, para a Company estornar à mão.

`refund_status`: `pending` (o Pix estava pago: devolver), `verify` (estava pendente, mas o Contact pode ter pago:
conferir no banco), `refunded` (devolvido) e `dismissed` (conferido, nada a devolver). As baixas são idempotentes.
Escopo pelas Instances do usuário (`instance_ids_for_user`); fora dele a resposta é 404.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.access import instance_ids_for_user
from app.api.deps import get_current_user, get_db
from app.models import CustomerOrder, PaymentRecord, User

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
