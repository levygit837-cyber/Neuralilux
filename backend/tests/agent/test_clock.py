"""Hora local da Company: um fuso quebrado nunca derruba o Turn."""

import pytest

from app.agent import clock
from app.models import Company


@pytest.mark.parametrize("zone", ["../x", "", None, "Foo/Bar", "/etc/passwd"])
def test_invalid_company_timezone_falls_back_to_the_default_zone(zone):
    assert clock.company_zone(Company(name="Pizzaria", timezone=zone)).key == "America/Sao_Paulo"
