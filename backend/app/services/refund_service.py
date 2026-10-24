"""Baixa de estornos Pix. Comita uma vez."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import PaymentRecord


def close_refund(db: Session, record: PaymentRecord, final: str) -> None:
    """Dá baixa no estorno (`refunded` ou `dismissed`)."""
    record.refund_status = final
    record.refunded_at = datetime.now(timezone.utc)
    db.commit()
