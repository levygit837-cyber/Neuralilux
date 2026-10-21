"""Pix do Pack: payload EMV "copia e cola" e Payment Record único por Order."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.models import Company, CustomerOrder, PaymentRecord


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


def txid_for(order: CustomerOrder) -> str:
    """Identificador do Pix: o número do Order sem separadores (alfanumérico, até 25 caracteres)."""
    return re.sub(r"[^A-Za-z0-9]", "", order.order_number)[:25]


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
        .filter(PaymentRecord.order_id == order_id, PaymentRecord.payment_method == "pix")
        .order_by(PaymentRecord.created_at, PaymentRecord.id)
        .first()
    )


def ensure_payment_record(db: Session, order: CustomerOrder, company: Company) -> PaymentRecord:
    """Devolve o Payment Record Pix do Order, criando-o só na primeira vez.

    O valor é o `total_amount` real do Order e a chave é a da Company dona dele. O dedup tem duas
    camadas: a leitura prévia e o índice único parcial `uq_payment_records_order_pix`. Se duas
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
    record = PaymentRecord(
        order_id=order_id,
        conversation_id=order.conversation_id,
        amount=amount,
        pix_key=company.pix_key,
        qr_code_data=build_emv(
            key=company.pix_key,
            amount=amount,
            txid=txid_for(order),
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
