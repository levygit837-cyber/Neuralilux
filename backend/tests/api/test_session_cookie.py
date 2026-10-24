"""Sessão do navegador no cookie httpOnly: atributos, logout, Bearer, Origin nas mutações e handshake do socket (#100)."""
from datetime import timedelta

import pytest
import socketio
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.auth_cookie import AUTH_COOKIE_NAME
from app.core.config import settings
from app.realtime import socket as socket_module
from app.main import socket_app
from tests.access_helpers import make_user
from tests.api.test_auth_tokens import _bad_tokens, _token

EMAIL = "dono@example.com"
ALLOWED_ORIGIN = settings.CORS_ORIGINS[0]
EVIL_ORIGIN = "https://evil.example.com"


@pytest.fixture
def owner(client, db):
    make_user(client, db, EMAIL)
    return EMAIL


def _login(client):
    return client.post("/api/v1/auth/login", data={"username": EMAIL, "password": "testpass123"})


def _set_cookie(response) -> str:
    return next(h for h in response.headers.get_list("set-cookie") if h.startswith(f"{AUTH_COOKIE_NAME}="))


def test_login_sets_an_httponly_lax_cookie_with_the_jwt_lifetime(client, owner):
    response = _login(client)
    header = _set_cookie(response).lower()
    assert "httponly" in header and "samesite=lax" in header and "path=/" in header
    assert f"max-age={settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60}" in header
    assert "secure" not in header  # development
    assert response.json()["access_token"]  # sem Origin (script, e2e): o corpo também traz o token


def test_browser_login_gets_only_the_cookie_and_the_body_has_no_token(client, owner):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": EMAIL, "password": "testpass123"},
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert response.status_code == 200
    assert "access_token" not in response.json()
    assert client.cookies.get(AUTH_COOKIE_NAME)
    assert client.get("/api/v1/auth/me").status_code == 200  # a sessão vive no cookie


def test_cookie_is_secure_outside_development(client, owner, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert "secure" in _set_cookie(_login(client)).lower().split("; ")


def test_cookie_authenticates_without_authorization_header(client, owner):
    _login(client)
    assert client.cookies.get(AUTH_COOKIE_NAME)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200 and response.json()["email"] == EMAIL


def test_logout_clears_the_cookie_and_the_session_ends(client, owner):
    _login(client)
    response = client.post("/api/v1/auth/logout", headers={"Origin": ALLOWED_ORIGIN})
    assert response.status_code == 204
    cleared = _set_cookie(response).lower()
    assert "max-age=0" in cleared and "httponly" in cleared and "samesite=lax" in cleared
    assert client.cookies.get(AUTH_COOKIE_NAME) is None
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_works_without_a_valid_session(client):
    assert client.post("/api/v1/auth/logout").status_code == 204


def test_bearer_still_works_without_cookie(client, owner):
    token = _login(client).json()["access_token"]
    client.cookies.clear()
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_bearer_wins_over_the_cookie(client, owner):
    client.cookies.set(AUTH_COOKIE_NAME, _bad_tokens()["garbage"])
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {_token()}"}).status_code == 200


@pytest.mark.parametrize("kind", list(_bad_tokens()))
def test_forged_or_expired_cookie_is_refused(client, owner, kind):
    client.cookies.set(AUTH_COOKIE_NAME, _bad_tokens()[kind])
    assert client.get("/api/v1/auth/me").status_code == 401


def test_expired_cookie_is_refused(client, owner):
    client.cookies.set(AUTH_COOKIE_NAME, _token(expires_in=timedelta(seconds=-1)))
    assert client.get("/api/v1/auth/me").status_code == 401


def test_no_credentials_is_401(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_mutation_from_a_disallowed_origin_is_refused_even_with_a_valid_cookie(client, owner):
    _login(client)
    response = client.post("/api/v1/auth/logout", headers={"Origin": EVIL_ORIGIN})
    assert response.status_code == 403 and response.json() == {"detail": "Origin not allowed"}
    assert client.get("/api/v1/auth/me").status_code == 200  # a sessão não foi encerrada


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_every_mutating_method_checks_the_origin(client, owner, method):
    _login(client)
    response = client.request(method, "/api/v1/companies/qualquer", headers={"Origin": EVIL_ORIGIN})
    assert response.status_code == 403


def test_origin_null_is_refused(client, owner):
    _login(client)
    assert client.post("/api/v1/auth/logout", headers={"Origin": "null"}).status_code == 403


def test_mutation_from_an_allowed_origin_goes_through(client, owner):
    _login(client)
    assert client.post("/api/v1/auth/logout", headers={"Origin": ALLOWED_ORIGIN}).status_code == 204


def test_mutation_without_origin_goes_through_for_non_browser_clients(client, owner):
    token = _login(client).json()["access_token"]
    client.cookies.clear()
    assert client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}).status_code == 204


def test_safe_methods_do_not_check_the_origin(client, owner):
    _login(client)
    assert client.get("/api/v1/auth/me", headers={"Origin": EVIL_ORIGIN}).status_code == 200


async def _handshake(cookie: str | None, auth, monkeypatch, db):
    """Chama o handler `connect` real com o `environ` do handshake; `False` se recusou, ou a sessão salva."""
    monkeypatch.setattr(socket_module, "SessionLocal", sessionmaker(bind=db.get_bind()))
    server = socket_module.chat_socket_service.server
    saved: dict = {}

    async def save_session(sid, session, namespace=None):
        saved.update(session)

    monkeypatch.setattr(server, "save_session", save_session)
    environ = {"HTTP_COOKIE": cookie} if cookie is not None else {}
    try:
        await server.handlers["/"]["connect"]("sid-teste", environ, auth)
    except socketio.exceptions.ConnectionRefusedError:
        return False
    return saved


@pytest.mark.asyncio
async def test_socket_authenticates_through_the_cookie_at_handshake(client, db, owner, monkeypatch):
    session = await _handshake(f"outro=1; {AUTH_COOKIE_NAME}={_token()}", None, monkeypatch, db)
    assert session["email"] == EMAIL


@pytest.mark.asyncio
async def test_socket_refuses_forged_cookie(client, db, owner, monkeypatch):
    forged = _bad_tokens()["wrong_key"]
    assert await _handshake(f"{AUTH_COOKIE_NAME}={forged}", None, monkeypatch, db) is False


@pytest.mark.asyncio
async def test_socket_refuses_without_cookie_or_token(client, db, owner, monkeypatch):
    assert await _handshake(None, None, monkeypatch, db) is False
    assert await _handshake("outro=1", None, monkeypatch, db) is False


@pytest.mark.asyncio
async def test_socket_still_accepts_auth_token_for_non_browser_clients(client, db, owner, monkeypatch):
    session = await _handshake(None, {"token": _token()}, monkeypatch, db)
    assert session["email"] == EMAIL


def _engineio_handshake(origin: str):
    """GET de abertura do Engine.IO (polling), como o navegador faz antes de subir o WebSocket."""
    return TestClient(socket_app).get("/realtime/socket.io/?EIO=4&transport=polling", headers={"Origin": origin})


def test_socket_refuses_handshake_from_a_disallowed_origin():
    assert _engineio_handshake(EVIL_ORIGIN).status_code == 400


def test_socket_accepts_handshake_from_an_allowed_origin():
    assert _engineio_handshake(ALLOWED_ORIGIN).status_code == 200
