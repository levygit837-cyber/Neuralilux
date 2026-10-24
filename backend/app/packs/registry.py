"""Qual Pack atende cada Business Type (ADR 0004).

Um novo ramo entra aqui por `register_pack`; o núcleo (`app.agent`) não muda e não importa nada de `app.packs`.
Quem monta um Turn (`app.whatsapp`) pede `packs_for(company)` e entrega a lista ao executor.
"""

from collections.abc import Callable

from app.agent.contracts import Pack, Tool, ToolContext
from app.agent.core_tools import core_tools
from app.agent.pack_hooks import validate_pack_hooks
from app.models import BusinessType, Company
from app.packs.catalog_orders.pack import CatalogOrdersPack

PACKS_BY_BUSINESS_TYPE: dict[str, Callable[[], Pack]] = {}


def register_pack(business_type_slug: str, factory: Callable[[], Pack]) -> None:
    """Associa um Pack a um Business Type. Falha se o Pack declara um gancho `on_*` que o núcleo não conhece."""
    validate_pack_hooks(factory())
    PACKS_BY_BUSINESS_TYPE[business_type_slug] = factory


register_pack("restaurant", CatalogOrdersPack)


class CorePack:
    """As Tools do núcleo, que todo Agent tem independentemente do Business Type."""

    name = "core"

    def tools(self) -> list[Tool]:
        return core_tools()

    def system_prompt_section(self, ctx: ToolContext) -> str:
        return ""

    def turn_context(self, ctx: ToolContext) -> str:
        return ""


def pack_for_company(company: Company) -> Pack | None:
    """O Pack do Business Type da Company; `None` se o ramo ainda não tem Pack."""
    business_type: BusinessType | None = company.business_type
    factory = PACKS_BY_BUSINESS_TYPE.get(business_type.slug) if business_type else None
    return factory() if factory else None


def packs_for(company: Company) -> list[Pack]:
    """Os Packs de um Turn da Company: o núcleo primeiro, depois o do ramo (se houver)."""
    pack = pack_for_company(company)
    return [CorePack(), pack] if pack else [CorePack()]
