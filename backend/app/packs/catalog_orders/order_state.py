"""Estado do Order da Conversation: busca, criação, campos faltantes e a visão devolvida ao modelo."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.agent.contracts import ToolContext, ToolResult
from app.models import Company, Contact, CustomerOrder
from app.packs.catalog_orders.totals import subtotal
from app.packs.catalog_orders.validation import OrderError

ACTIVE_STATUSES = ("open", "collecting_data", "ready_for_confirmation")
STATUS_LABELS = {
    "open": "em montagem",
    "collecting_data": "em montagem",
    "ready_for_confirmation": "em montagem",
    "closed": "recebido, aguardando preparo",
    "in_production": "em preparo",
    "sent": "saiu para entrega",
    "delivered": "entregue",
    "cancelled": "cancelado",
    "abandoned": "abandonado, não foi finalizado",
}


REOPENED_LABEL = "em alteração, aguardando nova confirmação"


def is_reopened(order: CustomerOrder) -> bool:
    """Order confirmado que voltou à montagem por `alterar_pedido` e ainda não foi reconfirmado (`closed_at` fica)."""
    return order.status in ACTIVE_STATUSES and order.closed_at is not None


def ok(data: dict[str, Any]) -> ToolResult:
    return ToolResult(content=json.dumps(data, ensure_ascii=False))


def error(message: str) -> ToolResult:
    return ToolResult(content=json.dumps({"erro": message}, ensure_ascii=False), is_error=True)


def get_company(ctx: ToolContext) -> Company:
    company = ctx.db.get(Company, ctx.company_id)
    if company is None:
        raise OrderError("Empresa não encontrada.")
    return company


def active_order(ctx: ToolContext) -> CustomerOrder | None:
    return (
        ctx.db.query(CustomerOrder)
        .filter(CustomerOrder.conversation_id == ctx.conversation_id, CustomerOrder.status.in_(ACTIVE_STATUSES))
        .order_by(CustomerOrder.created_at.desc())
        .first()
    )


def new_order(ctx: ToolContext) -> CustomerOrder:
    contact = ctx.db.get(Contact, ctx.contact_id)
    now = datetime.now(timezone.utc)  # explícito: a ordem entre Orders da mesma Conversation decide o que é "mais recente"
    order = CustomerOrder(
        opened_at=now,
        created_at=now,
        order_number=f"{now:%Y%m%d}-{uuid.uuid4().hex[:6].upper()}",
        conversation_id=ctx.conversation_id,
        instance_id=ctx.instance_id,
        contact_id=ctx.contact_id,
        remote_jid=ctx.remote_jid,
        customer_phone=contact.phone_number if contact else None,
        status="open",
        delivery_fee=Decimal("0.00"),
        total_amount=Decimal("0.00"),
    )
    ctx.db.add(order)
    ctx.db.flush()
    return order


def missing_fields(order: CustomerOrder) -> list[str]:
    missing = []
    if not order.customer_name:
        missing.append("nome")
    if not order.delivery_type:
        missing.append("tipo_entrega")
    elif order.delivery_type == "entrega" and not order.customer_address:
        missing.append("endereco")
    if not order.payment_method:
        missing.append("forma_pagamento")
    return missing


def view(order: CustomerOrder) -> dict[str, Any]:
    return {
        "numero": order.order_number,
        "status": order.status,
        "status_descricao": REOPENED_LABEL if is_reopened(order) else STATUS_LABELS.get(order.status, order.status),
        "em_alteracao": is_reopened(order),
        "itens": [
            {
                "item_id": line.menu_item_id,
                "nome": line.item_name,
                "quantidade": line.quantity,
                "preco_unitario": float(line.unit_price),
                "subtotal": float(line.subtotal_price),
                "observacao": line.notes,
            }
            for line in order.items
        ],
        "subtotal": float(subtotal(order)),
        "taxa_entrega": float(order.delivery_fee or 0),
        "total": float(order.total_amount or 0),
        "nome": order.customer_name,
        "tipo_entrega": order.delivery_type,
        "endereco": order.customer_address,
        "forma_pagamento": order.payment_method,
        "troco_para": float(order.change_for) if order.change_for is not None else None,
        "faltando": missing_fields(order) if order.status in ACTIVE_STATUSES else [],
    }
