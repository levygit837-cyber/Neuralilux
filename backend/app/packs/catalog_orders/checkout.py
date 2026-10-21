"""Fechamento do Order: `definir_dados` (coleta validada) e `finalizar` (mínimo, troco e Pix)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.agent.contracts import ToolContext
from app.packs.catalog_orders import pix
from app.packs.catalog_orders.order_state import active_order, get_company, missing_fields, view
from app.packs.catalog_orders.totals import brl, cents, recompute, require_zone, subtotal
from app.packs.catalog_orders.validation import (
    DELIVERY_TYPES,
    PAYMENT_METHODS,
    OrderError,
    choice,
    validate_address,
    validate_name,
)

DATA_FIELDS = ("nome", "tipo_entrega", "forma_pagamento", "endereco", "troco_para")


def _change_for(order, raw: Any, payment: str | None):
    """Troco pedido: vale só para dinheiro; `None` limpa quando a forma de pagamento deixa de ser dinheiro."""
    change_for = order.change_for
    if raw is not None:
        try:
            change_for = cents(Decimal(str(raw)))
        except InvalidOperation:
            raise OrderError("troco_para deve ser um valor em reais.") from None
        if change_for <= 0:
            raise OrderError("troco_para deve ser maior que zero.")
        if payment != "dinheiro":
            raise OrderError("troco_para só vale para pagamento em dinheiro.")
    elif payment != "dinheiro":
        change_for = None
    return change_for


def _check_change_covers_total(change_for, total) -> None:
    if change_for is not None and change_for < total:
        raise OrderError(f"O troco é para {brl(change_for)}, menos que o total de {brl(total)}.")


def definir_dados(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    order = active_order(ctx)
    if order is None:
        raise OrderError("Não há pedido em aberto. Adicione um item antes de informar os dados.")
    if all(args.get(k) is None for k in DATA_FIELDS):
        raise OrderError("Informe ao menos um dado: nome, tipo_entrega, endereco, forma_pagamento ou troco_para.")
    company = get_company(ctx)

    name = validate_name(args["nome"]) if args.get("nome") is not None else order.customer_name
    delivery_type = (
        choice(args["tipo_entrega"], DELIVERY_TYPES, "tipo_entrega")
        if args.get("tipo_entrega") is not None
        else order.delivery_type
    )
    payment = (
        choice(args["forma_pagamento"], PAYMENT_METHODS, "forma_pagamento")
        if args.get("forma_pagamento") is not None
        else order.payment_method
    )
    if payment == "pix" and not company.pix_key:
        raise OrderError("Esta empresa não aceita Pix. Ofereça dinheiro ou cartão.")

    address = order.customer_address
    if delivery_type == "retirada":
        address = None
    elif args.get("endereco") is not None:
        address = validate_address(args["endereco"])
    if delivery_type == "entrega" and address:
        require_zone(ctx, address)

    change_for = _change_for(order, args.get("troco_para"), payment)

    order.customer_name = name
    order.delivery_type = delivery_type
    order.customer_address = address
    order.payment_method = payment
    order.change_for = change_for
    recompute(ctx, order)
    _check_change_covers_total(change_for, order.total_amount)
    ctx.db.commit()
    return {"pedido": view(order)}


def finalizar(ctx: ToolContext, _args: dict[str, Any]) -> dict[str, Any]:
    order = active_order(ctx)
    if order is None or not order.items:
        raise OrderError("O pedido está vazio. Adicione itens antes de finalizar.")
    missing = missing_fields(order)
    if missing:
        raise OrderError(f"Faltam dados para finalizar: {', '.join(missing)}.")
    company = get_company(ctx)

    if order.delivery_type == "entrega":
        require_zone(ctx, order.customer_address)
    recompute(ctx, order)

    minimum = cents(company.minimum_order) if company.minimum_order else None
    items_total = subtotal(order)
    if minimum and items_total < minimum:
        raise OrderError(
            f"Pedido mínimo de {brl(minimum)} em itens (sem a taxa de entrega); faltam {brl(minimum - items_total)}."
        )
    _check_change_covers_total(order.change_for, order.total_amount)
    if order.payment_method == "pix" and not company.pix_key:
        raise OrderError("Esta empresa não tem chave Pix cadastrada; não dá para fechar com Pix.")

    record = pix.ensure_payment_record(ctx.db, order, company) if order.payment_method == "pix" else None
    order.status = "closed"
    order.closed_at = datetime.now(timezone.utc)
    ctx.db.commit()

    result: dict[str, Any] = {
        "pedido": view(order),
        "mensagem": f"Pedido {order.order_number} confirmado. Total {brl(order.total_amount)}.",
    }
    if record is not None:
        result["pix"] = {
            "valor": float(record.amount),
            "chave": record.pix_key,
            "txid": pix.txid_for(order),
            "copia_e_cola": record.qr_code_data,
        }
    return result
