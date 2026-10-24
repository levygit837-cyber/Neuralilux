"""Cadastro: e-mail duplicado é 409 (também na corrida), Company inexistente é 422, e erro de banco não vaza (#83)."""
import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.core.database import Base
from app.main import app
from app.models import User
from app.services import user_service
from tests.access_helpers import make_company, make_user
from fastapi.testclient import TestClient


def _payload(email: str, **extra) -> dict:
    return {"email": email, "password": "testpass123", "full_name": "Novo", **extra}


def test_duplicate_email_is_409(client, db):
    assert client.post("/api/v1/auth/register", json=_payload("a@example.com")).status_code == 201
    response = client.post("/api/v1/auth/register", json=_payload("a@example.com"))
    assert response.status_code == 409
    assert db.query(User).filter(User.email == "a@example.com").count() == 1


def test_unknown_company_is_422_and_creates_nothing(client, db):
    admin = make_user(client, db, "admin@example.com", superuser=True)
    response = client.post(
        "/api/v1/auth/register", json=_payload("novo@example.com", company_id="nao-existe"), headers=admin
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Company not found"
    assert db.query(User).filter(User.email == "novo@example.com").first() is None


def test_known_company_still_registers(client, db):
    company = make_company(db, "Alvo")
    admin = make_user(client, db, "admin@example.com", superuser=True)
    response = client.post(
        "/api/v1/auth/register", json=_payload("novo@example.com", company_id=company.id), headers=admin
    )
    assert response.status_code == 201


def test_unexpected_database_error_does_not_leak_into_detail(client, db, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError('duplicate key value violates unique constraint "users_pkey" on table users')

    monkeypatch.setattr(user_service, "get_password_hash", explode)
    response = client.post("/api/v1/auth/register", json=_payload("b@example.com"))
    assert response.status_code == 500
    assert response.json()["detail"] == "Error creating user"


def test_integrity_error_that_is_not_the_email_is_500_never_409(client, db, monkeypatch):
    """Outra constraint estoura no commit e o e-mail continua livre após o rollback: não é duplicado."""

    def violate():
        raise IntegrityError("INSERT INTO users", {}, Exception("FOREIGN KEY constraint failed"))

    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", violate)
        response = client.post("/api/v1/auth/register", json=_payload("c@example.com"))
    assert response.status_code == 500
    assert response.json()["detail"] == "Error creating user"
    assert db.query(User).filter(User.email == "c@example.com").first() is None


def test_concurrent_registrations_of_the_same_email_give_one_201_and_one_409(tmp_path, monkeypatch):
    """Duas requisições passam juntas pela checagem de e-mail; a constraint única decide, nunca um 500."""
    engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine, autoflush=False)

    def get_db_per_request():
        session = sessions()
        try:
            yield session
        finally:
            session.close()

    barrier = threading.Barrier(2, timeout=10)
    original = user_service.get_user_by_email
    waited = threading.local()

    def check_then_wait(db, email):
        found = original(db, email)
        if not getattr(waited, "done", False):  # só a checagem inicial; a releitura após o conflito passa direto
            waited.done = True
            barrier.wait()  # as duas requisições já viram "e-mail livre" antes de qualquer insert
        return found

    monkeypatch.setattr(user_service, "get_user_by_email", check_then_wait)
    app.dependency_overrides[get_db] = get_db_per_request
    statuses: list[int] = []

    def register():
        statuses.append(TestClient(app).post("/api/v1/auth/register", json=_payload("corrida@example.com")).status_code)

    threads = [threading.Thread(target=register) for _ in range(2)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()

    assert sorted(statuses) == [201, 409]
