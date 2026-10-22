"""Pix do Pack: payload EMV "copia e cola" e Payment Record único por Order."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.clock import utc_now
from app.models import Company, CustomerOrder, PaymentRecord

VALID_STATUSES = ("pending", "paid")  # os demais (cancelled, superseded, expired) não cobram mais nada


class PixError(ValueError):
    """Não dá para gerar o Pix com os dados da Company/Order (ex: chave ausente ou longa demais)."""


def _tlv(tag: str, value: str) -> str:
    if len(value) > 99:
        raise PixError(f"campo EMV {tag} com {len(value)} caracteres; o máximo é 99")
    return f"{tag}{len(value):02d}{value}"


def crc16(payload: str) -> str:
    """CRC16/CCITT-FALSE exigido pelo BR Code (campo 63)."""
    crc = 0xFFFF
    for byte in payload.encode("ascii"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def _ascii_upper(text: str, limit: int) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9 ]", "", plain).upper().strip()[:limit]


TXID_MAX = 25


def txid_for(order: CustomerOrder, revision: int = 0) -> str:
    """Identificador do Pix: o número do Order sem separadores (alfanumérico, até 25 caracteres).

    Cada Pix novo do mesmo Order (depois de uma alteração) leva o sufixo `R<revisão>`, para o banco nunca ver o
    mesmo txid em cobranças de valores diferentes. A revisão 0 não tem sufixo.
    """
    base = re.sub(r"[^A-Za-z0-9]", "", order.order_number)
    suffix = f"R{revision}" if revision else ""
    return base[: TXID_MAX - len(suffix)] + suffix


def build_emv(*, key: str, amount: Decimal, txid: str, merchant_name: str, merchant_city: str) -> str:
    account = _tlv("00", "br.gov.bcb.pix") + _tlv("01", key)
    body = (
        _tlv("00", "01")
        + _tlv("01", "12")
        + _tlv("26", account)
        + _tlv("52", "0000")
        + _tlv("53", "986")
        + _tlv("54", f"{amount.quantize(Decimal('0.01'))}")
        + _tlv("58", "BR")
        + _tlv("59", _ascii_upper(merchant_name, 25) or "LOJA")
        + _tlv("60", _ascii_upper(merchant_city, 15) or "BRASIL")
        + _tlv("62", _tlv("05", txid))
        + "6304"
    )
    return body + crc16(body)


def _existing_record(db: Session, order_id: str) -> PaymentRecord | None:
    return (
        db.query(PaymentRecord)
        .filter(
            PaymentRecord.order_id == order_id,
            PaymentRecord.payment_method == "pix",
            PaymentRecord.status.in_(VALID_STATUSES),
        )
        .order_by(PaymentRecord.created_at, PaymentRecord.id)
        .first()
    )


def valid_records(db: Session, order: CustomerOrder) -> list[PaymentRecord]:
    return (
        db.query(PaymentRecord)
        .filter(
            PaymentRecord.order_id == order.id,
            PaymentRecord.payment_method == "pix",
            PaymentRecord.status.in_(VALID_STATUSES),
        )
        .all()
    )


def invalidate_records(db: Session, order: CustomerOrder, status: str) -> list[PaymentRecord]:
    """Tira de circulação o Pix válido do Order (`cancelled` no cancelamento, `superseded` na alteração).

    O sistema não detecta pagamento (nada marca um Pix como `paid`), então o Contact pode ter pago um Pix ainda
    `pending`. Por isso todo Pix invalidado entra na lista de estornos da Company: `refund_status="pending"` se
    estava `paid` (devolver) e `"verify"` se estava `pending` (conferir no banco se o Contact pagou, e devolver
    só nesse caso). Não faz `commit`.
    """
    records = valid_records(db, order)
    now = utc_now()
    for record in records:
        record.refund_status = "pending" if record.status == "paid" else "verify"
        record.refund_flagged_at = now
        record.status = status
    db.flush()
    return records


def revive_record(db: Session, record_id: str, status: str) -> None:
    """Devolve a validade ao Pix que uma alteração tinha substituído (a alteração foi desfeita) e limpa o estorno."""
    record = db.get(PaymentRecord, record_id)
    if record is not None and record.status == "superseded":
        record.status = status
        record.refund_status = None
        record.refund_flagged_at = None
        db.flush()


def ensure_payment_record(db: Session, order: CustomerOrder, company: Company) -> PaymentRecord:
    """Devolve o Payment Record Pix válido do Order, criando-o se não houver (primeira vez ou depois de uma alteração).

    O valor é o `total_amount` real do Order e a chave é a da Company dona dele. O dedup tem duas
    camadas: a leitura prévia e o índice único parcial `uq_payment_records_order_pix` (só Pix `pending`/`paid`). Se duas
    chamadas concorrentes passarem pela leitura, a segunda perde no índice, faz rollback e relê o
    registro vencedor. Levanta `PixError` quando o Pix não pode ser gerado.
    """
    order_id = order.id
    existing = _existing_record(db, order_id)
    if existing:
        return existing
    if not company.pix_key:
        raise PixError("a empresa não tem chave Pix cadastrada")

    amount = Decimal(order.total_amount).quantize(Decimal("0.01"))
    revision = db.query(PaymentRecord).filter(PaymentRecord.order_id == order_id, PaymentRecord.payment_method == "pix").count()
    txid = txid_for(order, revision)
    record = PaymentRecord(
        order_id=order_id,
        conversation_id=order.conversation_id,
        amount=amount,
        pix_key=company.pix_key,
        txid=txid,
        qr_code_data=build_emv(
            key=company.pix_key,
            amount=amount,
            txid=txid,
            merchant_name=company.name,
            merchant_city=company.address_city or "",
        ),
        status="pending",
        payment_method="pix",
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        winner = _existing_record(db, order_id)
        if winner is None:
            raise
        return winner
    return record
