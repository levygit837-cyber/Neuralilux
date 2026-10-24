"""Tool `condicoes_pedido`: como a Company recebe pedidos (entrega, pedido mínimo e pagamento).

Estes dados eram da Tool `info_empresa` do núcleo; o núcleo não conhece ramo (ADR 0004), então vivem no Pack.
Sempre da Company do contexto.
"""

from __future__ import annotations

from typing import Any

from app.agent.contracts import Tool, ToolContext, ToolResult
from app.packs.catalog_orders.order_state import error, get_company, ok
from app.packs.catalog_orders.totals import active_zones, neighborhood_names
from app.packs.catalog_orders.validation import OrderError


def payment_methods(pix_key: str | None) -> list[str]:
    """Pix só aparece se a Company tem chave cadastrada; dinheiro e cartão valem sempre."""
    return (["pix"] if pix_key else []) + ["dinheiro", "cartao"]


async def _condicoes_pedido(ctx: ToolContext, _args: dict[str, Any]) -> ToolResult:
    try:
        company = get_company(ctx)
    except OrderError as exc:
        return error(str(exc))
    zones = sorted(active_zones(ctx), key=lambda zone: zone.name or "")
    return ok(
        {
            "formas_pagamento": payment_methods(company.pix_key),
            "chave_pix": company.pix_key,
            "pedido_minimo": float(company.minimum_order) if company.minimum_order is not None else None,
            "taxas_entrega": [
                {"zona": zone.name, "bairros": neighborhood_names(zone), "taxa": float(zone.delivery_fee)}
                for zone in zones
            ],
        }
    )


def condicoes_pedido_tool() -> Tool:
    return Tool(
        name="condicoes_pedido",
        description=(
            "Condições para pedir na empresa: formas de pagamento, chave Pix, pedido mínimo e taxas de entrega "
            "por zona (com os bairros de cada uma). Use para responder sobre taxa de entrega, bairros atendidos, "
            "pedido mínimo ou como pagar."
        ),
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        handler=_condicoes_pedido,
    )
