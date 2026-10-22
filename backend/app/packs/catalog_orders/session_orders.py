"""Order e Session (ADR 0007): abandono ao abrir a Session nova, aviso ao Agent e retomada pedida pelo Contact.

Um Order aberto numa Session anterior vira `abandoned` e nunca volta a ser montado sozinho: `active_order`
só enxerga os status ativos. Se o Contact quiser o mesmo pedido, `retomar_pedido` cria um Order novo a
partir dos itens do abandonado, com os preços de hoje.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agent.contracts import ToolContext
from app.models import CustomerOrder, CustomerOrderItem
from app.packs.catalog_orders import changes
from app.packs.catalog_orders.items import catalog_item
from app.packs.catalog_orders.order_state import ACTIVE_STATUSES, active_order, is_reopened, new_order, view
from app.packs.catalog_orders.totals import brl, cents, recompute, subtotal
from app.packs.catalog_orders.validation import OrderError

ABANDONED = "abandoned"

NOTE_TEMPLATE = """\
## Pedido abandonado

Em um atendimento anterior o cliente deixou o pedido {number} sem finalizar: {lines}. Total dos itens: {total}.
Ele NÃO está em andamento e não vale como pedido atual. Se o cliente fizer um pedido novo, comece do zero
com `adicionar_item`. Se ele falar do pedido anterior ("o mesmo de ontem", "continua aquele"), ou se fizer
sentido oferecer, pergunte se quer retomar e, com o "sim", use `gerenciar_pedido` com a ação `retomar_pedido`.
Não use os itens dele antes disso.\
"""


def abandon_active_orders(db: Session, conversation_id: str) -> None:
    """Order em montagem vira `abandoned`; o confirmado e reaberto por `alterar_pedido` nunca é perdido.

    Sem a alteração reconfirmada, ele volta ao estado confirmado (`changes.restore_confirmed`); sem snapshot
    continua reaberto, visível como "em alteração", mas não abandonado.
    """
    orders = (
        db.query(CustomerOrder)
        .filter(CustomerOrder.conversation_id == conversation_id, CustomerOrder.status.in_(ACTIVE_STATUSES))
        .all()
    )
    for order in orders:
        if is_reopened(order):
            changes.restore_confirmed(db, order)
        else:
            order.status = ABANDONED


def pending_abandoned(ctx: ToolContext) -> CustomerOrder | None:
    """O Order mais recente da Conversation, se está abandonado e tem itens.

    Qualquer Order criado depois dele (montado, fechado ou retomado) encerra a oferta.
    """
    latest = (
        ctx.db.query(CustomerOrder)
        .filter(CustomerOrder.conversation_id == ctx.conversation_id)
        .order_by(CustomerOrder.created_at.desc(), CustomerOrder.opened_at.desc())
        .first()
    )
    return latest if latest and latest.status == ABANDONED and latest.items else None


def prompt_note(ctx: ToolContext) -> str:
    order = pending_abandoned(ctx)
    if order is None:
        return ""
    lines = ", ".join(
        f"{line.quantity}x {line.item_name}" + (f" ({line.notes})" if line.notes else "") for line in order.items
    )
    return NOTE_TEMPLATE.format(number=order.order_number, lines=lines, total=brl(subtotal(order)))


def retomar_pedido(ctx: ToolContext, _args: dict[str, Any]) -> dict[str, Any]:
    if active_order(ctx) is not None:
        raise OrderError("Já existe um pedido em montagem. Continue nele ou remova os itens antes de retomar o anterior.")
    old = pending_abandoned(ctx)
    if old is None:
        raise OrderError("Não há pedido abandonado para retomar. Monte um pedido novo com adicionar_item.")

    kept: list[tuple[CustomerOrderItem, Any]] = []
    unavailable: list[str] = []
    for line in old.items:
        try:
            kept.append((line, catalog_item(ctx, line.menu_item_id)))
        except OrderError:
            unavailable.append(line.item_name)
    if not kept:
        raise OrderError("Nenhum item do pedido anterior está disponível agora. Monte um pedido novo.")

    order = new_order(ctx)
    for position, (line, item) in enumerate(kept):
        order.items.append(
            CustomerOrderItem(
                menu_item_id=item.id,
                item_name=item.name,
                quantity=line.quantity,
                unit_price=cents(item.price),
                subtotal_price=0,
                notes=line.notes,
                sort_order=position,
            )
        )
    recompute(ctx, order)
    ctx.db.commit()
    data: dict[str, Any] = {"pedido": view(order)}
    if unavailable:
        data["indisponiveis"] = unavailable
    return data
