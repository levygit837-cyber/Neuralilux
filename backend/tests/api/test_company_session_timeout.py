"""O limite de inatividade da Session é configurável por Company (ADR 0007)."""

import pytest
from pydantic import ValidationError

from app.schemas.company import CompanyCreate, CompanyUpdate


@pytest.mark.parametrize("zone", ["../x", "", None, "Foo/Bar"])
def test_update_rejects_a_timezone_zoneinfo_cannot_load(zone):
    with pytest.raises(ValidationError):
        CompanyUpdate(timezone=zone)


@pytest.mark.parametrize("zone", ["../x", "", "Foo/Bar"])
def test_create_rejects_a_timezone_zoneinfo_cannot_load(zone):
    with pytest.raises(ValidationError):
        CompanyCreate(name="Pizzaria", business_type_id="bt-1", timezone=zone)

