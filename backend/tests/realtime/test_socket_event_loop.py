"""Event loop livre (#93): o handshake do Socket.IO (token -> usuário -> banco) não segura o loop."""
import time

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token
from app.realtime import socket as socket_module
from tests.access_helpers import make_user, user_id
from tests.loop_helpers import run_watched

pytestmark = pytest.mark.asyncio

EMAIL = "handshake@example.com"
LOOKUP_SECONDS = 0.25  # bem acima dos 100 ms do limite: no loop, o handshake seria um callback lento


async def test_handshake_does_not_block_the_event_loop(client, db, monkeypatch):
    make_user(client, db, EMAIL)
    service = socket_module.chat_socket_service
    real_lookup = service._get_user_from_token
    saved: dict[str, dict] = {}

    def slow_lookup(token):
        time.sleep(LOOKUP_SECONDS)  # a consulta ao banco (ou ao pool esgotado) demorando
        return real_lookup(token)

    async def save_session(sid, session, namespace=None):
        saved[sid] = session

    monkeypatch.setattr(service, "_get_user_from_token", slow_lookup)
    monkeypatch.setattr(service.server, "save_session", save_session)
    monkeypatch.setattr(socket_module, "SessionLocal", sessionmaker(bind=db.get_bind()))
    connect = service.server.handlers["/"]["connect"]
    token = create_access_token({"sub": EMAIL})

    _, slow = await run_watched(lambda: connect("sid-1", {}, {"token": token}))

    assert slow == []
    assert saved == {"sid-1": {"user_id": user_id(db, EMAIL), "email": EMAIL}}
