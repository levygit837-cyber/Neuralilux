"""Ações de itens do Order: `adicionar_item`, `remover_item` e `ver`."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.agent.contracts import ToolContext
from app.models import CustomerOrderItem, MenuCatalog, MenuItem
from app.packs.catalog_orders.order_state import active_order, new_order, view
from app.packs.catalog_orders.totals import cents, recompute
from app.packs.catalog_orders.validation import OrderError, positive_int


def turn_adds(ctx: ToolContext) -> set[tuple[str, str | None, int]]:
    """Adições (item, observação, quantidade) já feitas neste Turn; rascunho do Pack em `ctx.turn_state`."""
    return ctx.turn_state.setdefault("catalog_orders", {}).setdefault("adds", set())


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
    adds = turn_adds(ctx)
    turn_key = (item.id, note, quantity)
    if turn_key in adds:
        # Chamada idêntica já feita neste Turn (repetição do modelo): não duplica. Outra quantidade ou
        # observação é um pedido diferente e passa.
        return {"pedido": view(order), "mensagem": "Esse item já foi adicionado neste turno; nada mudou."}
    adds.add(turn_key)
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
    adds = turn_adds(ctx)
    adds.difference_update([key for key in adds if key[0] == item_id])  # tirou: adicionar de novo vale

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
