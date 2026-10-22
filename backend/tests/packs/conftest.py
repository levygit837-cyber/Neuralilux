from datetime import datetime, timezone

import pytest

from app.packs.catalog_orders import checkout

# Segunda 20:00 em Fortaleza (UTC-3, sem horário de verão): dentro do expediente de `pack_helpers.BUSINESS_HOURS`.
OPEN_NOW = datetime(2026, 10, 19, 23, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def company_is_open(monkeypatch):
    """Os testes de Pack não dependem do relógio real; os de horário sobrescrevem `checkout.utc_now`."""
    monkeypatch.setattr(checkout, "utc_now", lambda: OPEN_NOW)
