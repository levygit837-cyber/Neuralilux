"""Token → usuário: HTTP e handshake do Socket.IO usam a mesma regra e recusam token ruim e usuário inativo (#83)."""
import warnings
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import socketio
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import create_access_token
from app.models import User
from app.realtime import socket as socket_module
from tests.access_helpers import make_user


EMAIL = "dono@example.com"
# Emitido pelo python-jose 3.5.0 (HS256, sub=legado@example.com, exp=2100-01-01) antes da troca por PyJWT.
LEGACY_KEY = "chave-fixa-do-teste-de-token-legado-0123456789"
LEGACY_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJsZWdhZG9AZXhhbXBsZS5jb20iLCJleHAiOjQxMDI0NDQ4MDB9."
    "PXLfg4wQBfdkomJoF8Arp7Q96pS5azQ1td7vlvjNr8c"
)


def _token(sub=EMAIL, key=None, expires_in=timedelta(minutes=5)) -> str:
    claims = {"exp": datetime.now(timezone.utc) + expires_in}
    if sub is not None:
        claims["sub"] = sub
    return jwt.encode(claims, key or settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _tampered() -> str:
    header, payload, signature = _token().split(".")
    flipped = "A" if signature[0] != "A" else "B"
    return ".".join((header, payload, flipped + signature[1:]))


def _token_with_algorithm(algorithm: str) -> str:
    """Token com `sub` válido e a chave certa, mas assinado por um algoritmo que o servidor não aceita."""
    claims = {"sub": EMAIL, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    with warnings.catch_warnings():
        # A SECRET_KEY de teste tem menos de 64 bytes, o mínimo que o PyJWT recomenda para HS512. O teste precisa
        # justamente da mesma chave do servidor com outro algoritmo, então o aviso é esperado só neste encode.
        warnings.simplefilter("ignore", jwt.warnings.InsecureKeyLengthWarning)
        return jwt.encode(claims, settings.SECRET_KEY, algorithm=algorithm)


def _bad_tokens() -> dict[str, str]:
    return {
        "expired": _token(expires_in=timedelta(minutes=-5)),
        "tampered": _tampered(),
        "wrong_key": _token(key="outra-chave-que-nao-e-a-do-servidor-0123456789"),
        "unknown_sub": _token(sub="ninguem@example.com"),
        "no_sub": _token(sub=None),
        "garbage": "isso-nao-e-um-jwt",
        "alg_none": jwt.encode({"sub": EMAIL, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, None, algorithm="none"),
        "wrong_alg_hs512": _token_with_algorithm("HS512"),
    }


@pytest.fixture
def owner(client, db):
    make_user(client, db, EMAIL)
    return db.query(User).filter(User.email == EMAIL).one()


async def _handshake(token: str | None, monkeypatch, db):
    """Chama o handler `connect` real; devolve `False` se recusou, ou a sessão salva se aceitou."""
    monkeypatch.setattr(socket_module, "SessionLocal", sessionmaker(bind=db.get_bind()))
    server = socket_module.chat_socket_service.server
    saved: dict = {}

    async def save_session(sid, session, namespace=None):
        saved.update(session)

    monkeypatch.setattr(server, "save_session", save_session)
    auth = {"token": token} if token is not None else None
    try:
        await server.handlers["/"]["connect"]("sid-teste", {}, auth)
    except socketio.exceptions.ConnectionRefusedError:
        return False
    return saved


@pytest.mark.parametrize("kind", list(_bad_tokens()))
def test_http_refuses_bad_token_with_401(client, owner, kind):
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {_bad_tokens()[kind]}"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("kind", list(_bad_tokens()))
@pytest.mark.asyncio
async def test_socket_refuses_bad_token(client, db, owner, monkeypatch, kind):
    assert await _handshake(_bad_tokens()[kind], monkeypatch, db) is False


def test_http_refuses_inactive_user_with_a_valid_token(client, db, owner):
    headers = {"Authorization": f"Bearer {_token()}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    owner.is_active = False
    db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


@pytest.mark.asyncio
async def test_socket_refuses_inactive_user_with_a_valid_token(client, db, owner, monkeypatch):
    assert (await _handshake(_token(), monkeypatch, db))["user_id"] == owner.id
    owner.is_active = False
    db.commit()
    assert await _handshake(_token(), monkeypatch, db) is False


def test_login_token_works_on_http(client, owner):
    login = client.post("/api/v1/auth/login", data={"username": EMAIL, "password": "testpass123"})
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert response.status_code == 200 and response.json()["email"] == EMAIL


def test_issued_token_has_sub_exp_and_the_configured_algorithm(owner):
    token = create_access_token({"sub": EMAIL})
    assert jwt.get_unverified_header(token)["alg"] == settings.ALGORITHM == "HS256"
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    assert claims["sub"] == EMAIL and claims["exp"] > datetime.now(timezone.utc).timestamp()


@pytest.mark.asyncio
async def test_token_issued_by_python_jose_before_the_swap_still_works(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", LEGACY_KEY)
    make_user(client, db, "legado@example.com")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {LEGACY_TOKEN}"})
    assert response.status_code == 200 and response.json()["email"] == "legado@example.com"
    assert (await _handshake(LEGACY_TOKEN, monkeypatch, db))["email"] == "legado@example.com"
