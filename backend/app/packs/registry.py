"""Qual Pack atende cada Business Type (ADR 0004).

Um novo ramo entra aqui como mais uma entrada do mapa; o núcleo não muda.
"""

from collections.abc import Callable

from app.agent.contracts import Pack
from app.models.models import BusinessType, Company
from app.packs.catalog_orders.pack import CatalogOrdersPack

PACKS_BY_BUSINESS_TYPE: dict[str, Callable[[], Pack]] = {
    "restaurant": CatalogOrdersPack,
}


def pack_for_company(company: Company) -> Pack | None:
    """O Pack do Business Type da Company; `None` se o ramo ainda não tem Pack."""
    business_type: BusinessType | None = company.business_type
    factory = PACKS_BY_BUSINESS_TYPE.get(business_type.slug) if business_type else None
    return factory() if factory else None
