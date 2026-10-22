"""O limite de inatividade da Session é configurável por Company (ADR 0007)."""

import pytest
from pydantic import ValidationError

from app.models import Company
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.services.company_service import update_company


def test_company_session_timeout_can_be_changed(db):
    company = Company(name="Pizzaria")
    db.add(company)
    db.commit()

    update_company(db, company.id, CompanyUpdate(session_timeout_minutes=45))

    db.expire_all()
    assert db.get(Company, company.id).session_timeout_minutes == 45


@pytest.mark.parametrize("minutes", [0, -5])
def test_session_timeout_must_be_positive(minutes):
    with pytest.raises(ValidationError):
        CompanyUpdate(session_timeout_minutes=minutes)


@pytest.mark.parametrize("zone", ["../x", "", None, "Foo/Bar"])
def test_update_rejects_a_timezone_zoneinfo_cannot_load(zone):
    with pytest.raises(ValidationError):
        CompanyUpdate(timezone=zone)


@pytest.mark.parametrize("zone", ["../x", "", "Foo/Bar"])
def test_create_rejects_a_timezone_zoneinfo_cannot_load(zone):
    with pytest.raises(ValidationError):
        CompanyCreate(name="Pizzaria", business_type_id="bt-1", timezone=zone)


def test_company_timezone_can_be_changed_to_a_valid_zone(db):
    company = Company(name="Pizzaria")
    db.add(company)
    db.commit()

    update_company(db, company.id, CompanyUpdate(timezone="America/Fortaleza"))

    db.expire_all()
    assert db.get(Company, company.id).timezone == "America/Fortaleza"
