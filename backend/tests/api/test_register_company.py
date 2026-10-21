"""POST /auth/register não deixa o anônimo escolher a Company (T10)."""
from app.models import User
from tests.access_helpers import make_company, make_user


def _payload(email: str, company_id: str | None = None) -> dict:
    body = {"email": email, "password": "testpass123", "full_name": "Novo"}
    if company_id:
        body["company_id"] = company_id
    return body


def test_anonymous_register_with_company_is_403_and_creates_nothing(client, db):
    company = make_company(db, "Alvo")
    response = client.post("/api/v1/auth/register", json=_payload("intruso@example.com", company.id))
    assert response.status_code == 403
    assert db.query(User).filter(User.email == "intruso@example.com").first() is None


def test_regular_user_cannot_register_into_a_company(client, db):
    company = make_company(db, "Alvo")
    headers = make_user(client, db, "comum@example.com")
    response = client.post("/api/v1/auth/register", json=_payload("novo@example.com", company.id), headers=headers)
    assert response.status_code == 403


def test_superuser_registers_user_into_a_company(client, db):
    company = make_company(db, "Alvo")
    admin = make_user(client, db, "admin@example.com", superuser=True)
    response = client.post("/api/v1/auth/register", json=_payload("novo@example.com", company.id), headers=admin)
    assert response.status_code == 201
    assert response.json()["company_id"] == company.id


def test_anonymous_register_without_company_still_works(client, db):
    response = client.post("/api/v1/auth/register", json=_payload("livre@example.com"))
    assert response.status_code == 201
    assert response.json()["company_id"] is None


def test_invalid_token_on_register_is_401(client, db):
    response = client.post(
        "/api/v1/auth/register", json=_payload("x@example.com"), headers={"Authorization": "Bearer lixo"}
    )
    assert response.status_code == 401
