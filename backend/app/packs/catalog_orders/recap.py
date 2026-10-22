"""Recapitulação do Order: o Contact precisa ver o pedido e confirmar num Turn seguinte antes de `finalizar`.

`recapitular` grava a impressão (`recap_signature`) do Order e o Turn em que ele foi apresentado. `finalizar`
só fecha se a impressão ainda bate (nada mudou depois) e se o Turn atual é posterior ao da recapitulação.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.agent.contracts import ToolContext
from app.models import CustomerOrder
from app.packs.catalog_orders.order_state import get_company, view
from app.packs.catalog_orders.validation import OrderError


def signature(order: CustomerOrder) -> str:
    """Impressão de tudo que o Contact vê na recapitulação: itens, observações, dados, taxa e total."""
    state = {
        "itens": [[l.menu_item_id, l.quantity, str(l.unit_price), l.notes or ""] for l in order.items],
        "nome": order.customer_name,
        "tipo_entrega": order.delivery_type,
        "endereco": order.customer_address,
        "forma_pagamento": order.payment_method,
        "troco_para": str(order.change_for) if order.change_for is not None else None,
        "taxa": str(order.delivery_fee),
        "total": str(order.total_amount),
    }
    return hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def require_confirmed_recap(ctx: ToolContext, order: CustomerOrder) -> None:
    if order.recap_signature is None:
        raise OrderError(
            "O cliente ainda não viu a recapitulação. Chame recapitular, mostre o pedido e peça a confirmação; "
            "só finalize quando ele confirmar na próxima mensagem."
        )
    if order.recap_signature != signature(order):
        raise OrderError(
            "O pedido mudou depois da recapitulação. Chame recapitular, mostre o pedido atualizado e peça a "
            "confirmação de novo."
        )
    if order.recap_turn_id == ctx.turn_id:
        raise OrderError(
            "A recapitulação acabou de ser apresentada, o cliente ainda não confirmou. Responda com a "
            "recapitulação e espere a confirmação dele na próxima mensagem."
        )


def recapitular(ctx: ToolContext, _args: dict[str, Any]) -> dict[str, Any]:
    # Import local: `checkout` importa este módulo.
    from app.packs.catalog_orders.checkout import validate_closable

    order = validate_closable(ctx, get_company(ctx))
    current = signature(order)
    if order.recap_signature != current:
        # Recapitular de novo sem mudança preserva o Turn original: a confirmação do Contact continua valendo.
        order.recap_signature = current
        order.recap_turn_id = ctx.turn_id
    ctx.db.commit()
    return {
        "pedido": view(order),
        "mensagem": "Mostre esta recapitulação ao cliente (itens, taxa, total e dados) e peça a confirmação. "
        "Só chame finalizar depois que ele confirmar.",
    }
