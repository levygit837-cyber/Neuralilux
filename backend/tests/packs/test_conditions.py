"""`condicoes_pedido`: entrega, Pix, pedido mínimo e pagamento, sempre da Company do contexto."""

import pytest
from pack_helpers import call, make_world, payload, tool_named

from app.agent.contracts import ToolContext
from app.packs.catalog_orders.pack import CatalogOrdersPack

pytestmark = pytest.mark.asyncio


@pytest.fixture
def world(db):
    return make_world(db)


def conditions():
    return tool_named(CatalogOrdersPack().tools(), "condicoes_pedido")


async def test_returns_the_zones_pix_and_minimum_of_the_context_company(world):
    data = payload(await call(conditions(), world.ctx))

    assert data["formas_pagamento"] == ["pix", "dinheiro", "cartao"]
    assert data["chave_pix"] == "pix@loja.example"
    assert data["pedido_minimo"] == 30.0
    assert data["taxas_entrega"] == [{"zona": "Centro", "bairros": ["Centro", "Aldeota"], "taxa": 5.0}]


async def test_never_leaks_another_company_or_a_legacy_zone(world):
    data = payload(await call(conditions(), world.ctx))

    assert "outra@pix.example" not in str(data)
    assert all(zone["zona"] not in ("Praia", "Legada") for zone in data["taxas_entrega"])


async def test_each_company_sees_its_own_data(db, world):
    other = world.other_company
    ctx = ToolContext(
        db=db,
        company_id=other.id,
        instance_id=world.ctx.instance_id,
        conversation_id=world.ctx.conversation_id,
        contact_id=world.ctx.contact_id,
        remote_jid=world.ctx.remote_jid,
    )

    data = payload(await call(conditions(), ctx))

    assert data["chave_pix"] == "outra@pix.example"
    assert data["pedido_minimo"] is None
    assert [zone["zona"] for zone in data["taxas_entrega"]] == ["Praia"]


async def test_without_pix_key_pix_is_not_offered(db):
    world = make_world(db, pix_key=None)

    data = payload(await call(conditions(), world.ctx))

    assert data["chave_pix"] is None
    assert data["formas_pagamento"] == ["dinheiro", "cartao"]


async def test_without_zones_the_list_is_empty(db):
    world = make_world(db, with_zone=False)

    assert payload(await call(conditions(), world.ctx))["taxas_entrega"] == []


async def test_inactive_zone_is_not_listed(db, world):
    from app.models import DeliveryZone

    db.query(DeliveryZone).filter(DeliveryZone.company_id == world.company.id).update({"is_active": False})
    db.commit()

    assert payload(await call(conditions(), world.ctx))["taxas_entrega"] == []


async def test_pack_prompt_points_to_the_pack_tool_for_rates_and_payments():
    section = CatalogOrdersPack().system_prompt_section(None)

    assert "condicoes_pedido" in section
    assert "estão em `info_empresa`" not in section
