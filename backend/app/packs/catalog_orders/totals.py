"""Zonas de entrega e total do Order: itens + taxa da zona, com o pedido mínimo sobre os itens."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.agent.contracts import ToolContext
from app.models import CustomerOrder, DeliveryZone
from app.packs.catalog_orders.catalog import words
from app.packs.catalog_orders.validation import OrderError


def cents(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def brl(value: Decimal | float) -> str:
    return f"R$ {Decimal(str(value)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _active_zones(ctx: ToolContext) -> list[DeliveryZone]:
    return (
        ctx.db.query(DeliveryZone)
        .filter(DeliveryZone.company_id == ctx.company_id, DeliveryZone.is_active.is_(True))
        .all()
    )


def _neighborhood_names(zone: DeliveryZone) -> list[str]:
    names = []
    for entry in zone.neighborhoods or []:
        text = entry.get("name") if isinstance(entry, dict) else entry
        if isinstance(text, str) and text.strip():
            names.append(text)
    return names


def find_zone(ctx: ToolContext, address: str) -> DeliveryZone | None:
    """Zona ativa da Company cujo bairro aparece (palavras inteiras) no endereço; vence o bairro mais longo."""
    address_words = words(address)
    best: tuple[int, DeliveryZone] | None = None
    for zone in _active_zones(ctx):
        for name in _neighborhood_names(zone):
            target = words(name)
            if not target:
                continue
            size = len(target)
            for start in range(len(address_words) - size + 1):
                if address_words[start : start + size] == target and (best is None or size > best[0]):
                    best = (size, zone)
    return best[1] if best else None


def require_zone(ctx: ToolContext, address: str) -> DeliveryZone:
    zone = find_zone(ctx, address)
    if zone:
        return zone
    active = _active_zones(ctx)
    if not active:
        raise OrderError("Entrega indisponível: não há bairro com zona de entrega cadastrado. Ofereça retirada.")
    neighborhoods = ", ".join(n for z in active for n in _neighborhood_names(z))
    raise OrderError(
        f"Não entregamos nesse bairro. Bairros atendidos: {neighborhoods}. Ofereça outro endereço ou retirada."
    )


def subtotal(order: CustomerOrder) -> Decimal:
    return sum((cents(line.unit_price) * line.quantity for line in order.items), Decimal("0.00"))


def recompute(ctx: ToolContext, order: CustomerOrder) -> None:
    """Total = itens + taxa da zona (só entrega com endereço numa zona da Company)."""
    for line in order.items:
        line.subtotal_price = cents(line.unit_price) * line.quantity
    fee = Decimal("0.00")
    if order.delivery_type == "entrega" and order.customer_address:
        zone = find_zone(ctx, order.customer_address)
        fee = cents(zone.delivery_fee) if zone else fee
    order.delivery_fee = fee
    order.total_amount = subtotal(order) + fee
