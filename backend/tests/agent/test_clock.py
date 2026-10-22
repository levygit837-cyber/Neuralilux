"""Hora local da Company: um fuso quebrado nunca derruba o Turn."""

from datetime import datetime, timezone

import pytest

from app.agent import clock
from app.models import Company


@pytest.mark.parametrize("zone", ["../x", "", None, "Foo/Bar", "/etc/passwd"])
def test_invalid_company_timezone_falls_back_to_the_default_zone(zone):
    assert clock.company_zone(Company(name="Pizzaria", timezone=zone)).key == "America/Sao_Paulo"


def test_valid_company_timezone_is_used():
    now = datetime(2026, 10, 22, 23, 30, tzinfo=timezone.utc)

    text = clock.time_context(Company(name="Pizzaria", timezone="America/Fortaleza"), now, None, None)

    assert "20:30 (fuso America/Fortaleza)" in text
