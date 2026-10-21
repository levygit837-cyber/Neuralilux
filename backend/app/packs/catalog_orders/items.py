"""Ações de itens do Order: `adicionar_item`, `remover_item` e `ver`."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.agent.contracts import ToolContext
from app.models import CustomerOrderItem, MenuCatalog, MenuItem
from app.packs.catalog_orders.order_state import active_order, new_order, view
from app.packs.catalog_orders.totals import cents, recompute
from app.packs.catalog_orders.validation import OrderError, positive_int


def catalog_item(ctx: ToolContext, item_id: Any) -> MenuItem:
    """Item de um catálogo ativo da Company do contexto e disponível (mesma regra de `buscar_cardapio`)."""
    item = (
        ctx.db.query(MenuItem)
        .join(MenuCatalog, MenuCatalog.id == MenuItem.catalog_id)
        .filter(
            MenuItem.id == str(item_id or ""),
            MenuCatalog.company_id == ctx.company_id,
            MenuCatalog.is_active.is_(True),
        )
        .first()
    )
    if item is None:
        raise OrderError("Item não encontrado no cardápio. Use buscar_cardapio e passe o id do item.")
    if not item.is_available or item.price is None:
        raise OrderError(f"{item.name} está indisponível no momento. Ofereça outro item.")
    return item


def adicionar_item(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    item = catalog_item(ctx, args.get("item_id"))
    quantity = positive_int(args.get("quantidade"), "quantidade", 1)
    note = " ".join(str(args.get("observacao") or "").split()) or None

    order = active_order(ctx) or new_order(ctx)
    line = next((l for l in order.items if l.menu_item_id == item.id and (l.notes or None) == note), None)
    if line:
        line.quantity += quantity
    else:
        order.items.append(
            CustomerOrderItem(
                menu_item_id=item.id,
                item_name=item.name,
                quantity=quantity,
                unit_price=cents(item.price),
                subtotal_price=Decimal("0.00"),
                notes=note,
                sort_order=len(order.items),
            )
        )
    recompute(ctx, order)
    ctx.db.commit()
    return {"pedido": view(order)}


def remover_item(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Tira o item do pedido: tudo, ou `quantidade` unidades somadas entre as linhas do mesmo item.

    O mesmo item pode ter várias linhas (uma por observação). Com `quantidade`, desconta da linha mais
    recente para a mais antiga e remove as linhas que zerarem.
    """
    order = active_order(ctx)
    item_id = str(args.get("item_id") or "")
    lines = [l for l in (order.items if order else []) if l.menu_item_id == item_id]
    if not lines:
        raise OrderError("Esse item não está no pedido.")
    to_remove = positive_int(args.get("quantidade"), "quantidade", None)

    if to_remove is None:
        to_remove = sum(l.quantity for l in lines)
    for line in reversed(lines):
        if to_remove <= 0:
            break
        taken = min(to_remove, line.quantity)
        line.quantity -= taken
        to_remove -= taken
        if line.quantity == 0:
            order.items.remove(line)
    recompute(ctx, order)
    ctx.db.commit()
    return {"pedido": view(order)}


def ver(ctx: ToolContext, _args: dict[str, Any]) -> dict[str, Any]:
    order = active_order(ctx)
    if order is None:
        return {"pedido": None, "mensagem": "Não há pedido em aberto."}
    return {"pedido": view(order)}
