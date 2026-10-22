"""O limite de inatividade da Session é configurável por Company (ADR 0007)."""

import pytest
from pydantic import ValidationError

from app.models import Company
from app.schemas.company import CompanyUpdate
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
