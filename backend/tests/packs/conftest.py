from datetime import datetime, timezone

import pytest
from pack_helpers import make_world, tool_named

from app.packs.catalog_orders import checkout
from app.packs.catalog_orders.pack import CatalogOrdersPack

# Segunda 20:00 em Fortaleza (UTC-3, sem horário de verão): dentro do expediente de `pack_helpers.BUSINESS_HOURS`.
OPEN_NOW = datetime(2026, 10, 19, 23, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def company_is_open(monkeypatch):
    """Os testes de Pack não dependem do relógio real; os de horário sobrescrevem `checkout.utc_now`."""
    monkeypatch.setattr(checkout, "utc_now", lambda: OPEN_NOW)


@pytest.fixture
def world(db):
    return make_world(db)


@pytest.fixture
def pedido(world):
    return tool_named(CatalogOrdersPack().tools(), "gerenciar_pedido")
