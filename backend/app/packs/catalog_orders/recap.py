"""Recapitulação do Order: o Contact precisa ver o pedido e confirmar numa Message posterior antes de `finalizar`.

`recapitular` grava a impressão (`recap_signature`) do Order e o Turn que a apresenta. Ela só passa a valer
quando a resposta desse Turn é enviada (`on_reply_delivered` grava `recap_delivered_at`): Turn que falha, fica
sem resposta ou tem a resposta descartada não deixa recapitulação válida. `finalizar` só fecha se a impressão
ainda bate (nada mudou depois) e se a Message que dispara o Turn chegou depois da entrega.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.agent.clock import as_utc
from app.agent.contracts import ToolContext
from app.models import Conversation, CustomerOrder
from app.packs.catalog_orders.order_state import ACTIVE_STATUSES
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


def set_recap(order: CustomerOrder, signature_: str | None, turn_id: str | None) -> None:
    """Registra (ou, com `None`, descarta) a Recap do Order. Nunca vale até a entrega da resposta (`mark_delivered`)."""
    order.recap_signature = signature_
    order.recap_turn_id = turn_id
    order.recap_delivered_at = None


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
    if order.recap_delivered_at is None:
        raise OrderError(
            "A recapitulação ainda não chegou ao cliente. Se você acabou de fazê-la, responda com ela e espere a "
            "confirmação na próxima mensagem; se uma resposta anterior falhou, chame recapitular de novo."
        )
    if ctx.trigger_at is not None and as_utc(ctx.trigger_at) <= as_utc(order.recap_delivered_at):
        raise OrderError(
            "A mensagem do cliente chegou antes de ele ver a recapitulação, então não vale como confirmação. "
            "Recapitule de novo e espere a confirmação na próxima mensagem."
        )


def recapitular(ctx: ToolContext, _args: dict[str, Any]) -> dict[str, Any]:
    # Import local: `checkout` importa este módulo.
    from app.packs.catalog_orders.checkout import validate_closable

    order = validate_closable(ctx, get_company(ctx))
    current = signature(order)
    if order.recap_signature != current or order.recap_delivered_at is None:
        # Recapitular de novo sem mudança, depois de entregue, mantém a entrega: a confirmação do Contact vale.
        set_recap(order, current, ctx.turn_id)
    ctx.db.commit()
    return {
        "pedido": view(order),
        "mensagem": "Mostre esta recapitulação ao cliente (itens, taxa, total e dados) e peça a confirmação. "
        "Só chame finalizar depois que ele confirmar.",
    }


def mark_delivered(db: Session, conversation: Conversation, turn_id: str, at: datetime) -> None:
    """A resposta do Turn `turn_id` saiu: a recapitulação que ele apresentou passa a valer."""
    updated = (
        db.query(CustomerOrder)
        .filter(
            CustomerOrder.conversation_id == conversation.id,
            CustomerOrder.status.in_(ACTIVE_STATUSES),
            CustomerOrder.recap_turn_id == turn_id,
            CustomerOrder.recap_delivered_at.is_(None),
        )
        .update({CustomerOrder.recap_delivered_at: at}, synchronize_session=False)
    )
    if updated:
        db.commit()
