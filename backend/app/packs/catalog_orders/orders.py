"""`gerenciar_pedido` e `status_pedido`: o Order do Contact dentro da Conversation.

Todo acesso é escopado: itens e zonas pela `ctx.company_id`, Order pela `ctx.conversation_id`,
histórico pelo `ctx.contact_id`. Nenhuma ação grava dado parcial: validou e falhou, nada muda.
As ações vivem em `items.py` (itens) e `checkout.py` (dados e fechamento).
"""

from __future__ import annotations

from typing import Any

from app.agent.contracts import Tool, ToolContext, ToolResult
from app.models import CustomerOrder
from app.packs.catalog_orders import checkout, items, session_orders
from app.packs.catalog_orders.order_state import error, ok, view
from app.packs.catalog_orders.pix import PixError
from app.packs.catalog_orders.validation import DELIVERY_TYPES, PAYMENT_METHODS, OrderError

ACTIONS = ["adicionar_item", "remover_item", "ver", "definir_dados", "finalizar", "retomar_pedido"]

_ACTION_HANDLERS = {
    "adicionar_item": items.adicionar_item,
    "remover_item": items.remover_item,
    "ver": items.ver,
    "definir_dados": checkout.definir_dados,
    "finalizar": checkout.finalizar,
    "retomar_pedido": session_orders.retomar_pedido,
}


async def _gerenciar_pedido(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    handler = _ACTION_HANDLERS.get(str(args.get("acao") or ""))
    if handler is None:
        return error(f"Ação inválida. Use: {', '.join(ACTIONS)}.")
    try:
        return ok(handler(ctx, args))
    except OrderError as exc:
        ctx.db.rollback()
        return error(str(exc))
    except PixError as exc:
        ctx.db.rollback()
        return error(f"Não foi possível gerar o Pix: {exc}. O pedido não foi fechado; ofereça outra forma de pagamento.")


async def _status_pedido(ctx: ToolContext, _args: dict[str, Any]) -> ToolResult:
    order = (
        ctx.db.query(CustomerOrder)
        .filter(CustomerOrder.contact_id == ctx.contact_id, CustomerOrder.instance_id == ctx.instance_id)
        .order_by(CustomerOrder.opened_at.desc(), CustomerOrder.created_at.desc())
        .first()
    )
    if order is None:
        return ok({"pedido": None, "mensagem": "Este cliente ainda não fez nenhum pedido."})
    return ok({"pedido": view(order)})


def gerenciar_pedido_tool() -> Tool:
    return Tool(
        name="gerenciar_pedido",
        description=(
            "Monta e fecha o pedido do cliente. Ações: adicionar_item (item_id vindo de buscar_cardapio, "
            "quantidade, observacao), remover_item (item_id, quantidade opcional), ver, definir_dados (nome, "
            "tipo_entrega, endereco, forma_pagamento, troco_para) e finalizar. Só finalize com o pedido e os "
            "dados completos; o total inclui a taxa de entrega e respeita o pedido mínimo. retomar_pedido recria, a partir "
            "do pedido abandonado de um atendimento anterior, um pedido novo, só depois de o cliente aceitar."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "acao": {"type": "string", "enum": ACTIONS},
                "item_id": {"type": "string", "description": "Id do item, vindo de buscar_cardapio."},
                "quantidade": {"type": "integer", "minimum": 1},
                "observacao": {"type": "string", "description": "Ex: 'sem cebola'."},
                "nome": {"type": "string", "description": "Nome do cliente."},
                "endereco": {"type": "string", "description": "Rua, número e bairro. Só para entrega."},
                "tipo_entrega": {"type": "string", "enum": DELIVERY_TYPES},
                "forma_pagamento": {"type": "string", "enum": PAYMENT_METHODS},
                "troco_para": {"type": "number", "description": "Valor da nota, se pagar em dinheiro e precisar de troco."},
            },
            "required": ["acao"],
            "additionalProperties": False,
        },
        handler=_gerenciar_pedido,
    )


def status_pedido_tool() -> Tool:
    return Tool(
        name="status_pedido",
        description=(
            "Mostra o último pedido deste cliente: status, itens e total. "
            "Use para 'cadê meu pedido', 'já saiu?' e perguntas parecidas."
        ),
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        handler=_status_pedido,
    )
