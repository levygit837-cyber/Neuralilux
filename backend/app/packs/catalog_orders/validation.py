"""Validação dos dados do pedido: o que o modelo informa nunca é gravado sem passar por aqui."""

from __future__ import annotations

import re
from typing import Any

from app.packs.catalog_orders.catalog import normalize, words

DELIVERY_TYPES = ["entrega", "retirada"]
PAYMENT_METHODS = ["pix", "dinheiro", "cartao"]

MIN_ADDRESS_LENGTH = 8
# Respostas de checkout que o modelo às vezes grava como se fossem o nome do cliente.
NOT_A_NAME = frozenset(
    "retirada retirar entrega entregar delivery pix dinheiro cartao credito debito sim nao ok confirmar "
    "confirmo finalizar cancelar".split()
)


class OrderError(Exception):
    """Pedido recusado; a mensagem volta ao modelo como `erro`."""


def validate_name(raw: Any) -> str:
    name = " ".join(str(raw or "").split())
    letters = sum(1 for c in name if c.isalpha())
    if letters < 2 or len(name) > 200:
        raise OrderError("Nome inválido: preciso do nome do cliente (pelo menos 2 letras).")
    if set(words(name)) <= NOT_A_NAME:
        raise OrderError(f"'{name}' não é um nome. Pergunte o nome do cliente.")
    return name


def validate_address(raw: Any) -> str:
    address = " ".join(str(raw or "").split())
    letters = sum(1 for c in address if c.isalpha())
    if len(address) < MIN_ADDRESS_LENGTH or letters < 3 or not re.search(r"\d", address):
        raise OrderError("Endereço inválido: preciso de rua, número e bairro (ex: 'Rua das Flores 123, Centro').")
    return address


def choice(raw: Any, allowed: list[str], field: str) -> str:
    value = normalize(str(raw or "")).strip()
    if value not in allowed:
        raise OrderError(f"{field} inválido: use {' ou '.join(allowed)}.")
    return value


def positive_int(raw: Any, field: str, default: int | None) -> int | None:
    if raw is None:
        return default
    try:
        if isinstance(raw, bool) or int(raw) != float(raw):
            raise ValueError
        value = int(raw)
    except (TypeError, ValueError):
        raise OrderError(f"{field} deve ser um número inteiro maior que zero.") from None
    if value < 1:
        raise OrderError(f"{field} deve ser um número inteiro maior que zero.")
    return value
