"""Business Type → Pack: qual conjunto de Tools o Agent recebe para cada Company."""

import pytest

from app.agent import executor
from app.agent.core_tools import core_tools
from app.models.models import BusinessType, Company
from app.packs.catalog_orders.pack import CatalogOrdersPack
from app.packs.registry import pack_for_company

CORE_TOOL_NAMES = sorted(tool.name for tool in core_tools())


def _company(db, slug):
    business_type = None
    if slug is not None:
        business_type = BusinessType(name=slug or "vazio", slug=slug)
        db.add(business_type)
        db.flush()
    company = Company(name="Empresa", business_type_id=business_type.id if business_type else None)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _tool_names(packs):
    return sorted(tool.name for pack in packs for tool in pack.tools())


def test_restaurant_recebe_o_pack_de_catalogo_e_pedidos_alem_do_nucleo(db):
    company = _company(db, "restaurant")

    assert isinstance(pack_for_company(company), CatalogOrdersPack)
    names = _tool_names(executor.packs_for(company))
    assert set(CORE_TOOL_NAMES) < set(names)
    assert "buscar_cardapio" in names


@pytest.mark.parametrize("slug", ["oficina", "", None], ids=["desconhecido", "vazio", "sem-business-type"])
def test_business_type_sem_pack_fica_so_com_as_tools_do_nucleo(db, slug):
    company = _company(db, slug)

    assert pack_for_company(company) is None
    assert _tool_names(executor.packs_for(company)) == CORE_TOOL_NAMES
