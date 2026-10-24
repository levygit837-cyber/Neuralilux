"""O que o painel salva é o que o Agent usa: `info_empresa`, `condicoes_pedido` e o fechamento do pedido leem a Company do banco."""

from datetime import datetime, timezone

import pytest
from pack_helpers import add_item, call, confirm_and_finalize, fill_delivery, make_world, order_of, payload, tool_named

from app.agent import clock
from app.agent.core_tools import core_tools
from app.packs.catalog_orders import checkout
from app.packs.catalog_orders.pack import CatalogOrdersPack
from tests.access_helpers import make_user

pytestmark = pytest.mark.asyncio


async def test_info_empresa_returns_what_the_panel_saved(client, db, monkeypatch):
    world = make_world(db, pix_key=None)
    owner = make_user(client, db, "dono@example.com", company=world.company)
    # Terça 01:00 em Fortaleza (UTC-3): ainda é a noite de segunda, que cruza a meia-noite.
    monkeypatch.setattr(clock, "utc_now", lambda: datetime(2026, 10, 20, 4, 0, tzinfo=timezone.utc))

    info = tool_named(core_tools(), "info_empresa")
    conditions = tool_named(CatalogOrdersPack().tools(), "condicoes_pedido")
    before = payload(await call(conditions, world.ctx))
    assert before["chave_pix"] is None and "pix" not in before["formas_pagamento"]

    response = client.put(
        f"/api/v1/companies/{world.company.id}",
        headers=owner,
        json={
            "phone": "(85) 98888-1111",
            "pix_key": "pagamentos@macedos.example",
            "minimum_order": "42.00",
            "business_hours": {"mon": [["19:00", "02:00"]]},
            "timezone": "America/Fortaleza",
        },
    )
    assert response.status_code == 200, response.text

    after = payload(await call(info, world.ctx))
    assert after["telefone"] == "(85) 98888-1111"
    assert after["horarios"]["segunda"] == "19:00-02:00"
    assert after["aberto_agora"] is True
    saved = payload(await call(conditions, world.ctx))
    assert saved["chave_pix"] == "pagamentos@macedos.example"
    assert "pix" in saved["formas_pagamento"]
    assert saved["pedido_minimo"] == 42.0


async def test_pix_is_accepted_at_closing_once_the_panel_saves_a_key(client, db, monkeypatch):
    # Segunda 20:00 em Fortaleza: dentro do expediente do cenário.
    monkeypatch.setattr(checkout, "utc_now", lambda: datetime(2026, 10, 19, 23, 0, tzinfo=timezone.utc))
    world = make_world(db, pix_key=None)
    owner = make_user(client, db, "dono@example.com", company=world.company)
    pedido = tool_named(CatalogOrdersPack().tools(), "gerenciar_pedido")
    await add_item(world, pedido, quantidade=2)

    refused = await fill_delivery(world, pedido, forma_pagamento="pix")
    assert refused.is_error

    client.put(f"/api/v1/companies/{world.company.id}", headers=owner, json={"pix_key": "pagamentos@macedos.example"})

    assert not (await fill_delivery(world, pedido, forma_pagamento="pix")).is_error
    closed = payload(await confirm_and_finalize(world, pedido))
    assert closed["pix"]["chave"] == "pagamentos@macedos.example"
    assert order_of(world).status == "closed"
