"""Event loop livre (#93): o login (bcrypt + banco) não segura o loop, então o health check responde junto.

O bcrypt roda com o custo de produção (12, ~0,2 s por hash): com o custo baixo da suíte o bloqueio não apareceria.
"""
import asyncio
import time

import httpx
import pytest
import pytest_asyncio

from app.core import security
from app.main import app
from app.api.deps import get_db
from app.models import User
from tests.conftest import TestingSessionLocal
from tests.loop_helpers import run_watched

pytestmark = pytest.mark.asyncio

LOGIN = "/api/v1/auth/login"
PASSWORD = "testpass123"
# Sem o bcrypt fora do loop, 10 logins seguram o loop por ~1,7 s seguidos (medido). Um host carregado descalona o prober
# em centenas de ms (0,61 s com load average 41), então o teto fica entre os dois: separa o bloqueio real do ruído.
HEALTH_CEILING_SECONDS = 1.0


@pytest_asyncio.fixture
async def web(db, monkeypatch):
    """ASGI no event loop do teste, uma Session por request (a `db` compartilhada não aguenta threads em paralelo)."""
    monkeypatch.setattr(security, "BCRYPT_ROUNDS", 12)
    for n in range(10):
        db.add(User(email=f"u{n}@example.com", hashed_password=security.get_password_hash(PASSWORD), is_active=True))
    db.commit()

    def per_request_session():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = per_request_session
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


def _login(web, n: int = 0):
    return web.post(LOGIN, data={"username": f"u{n}@example.com", "password": PASSWORD})


async def test_login_does_not_block_the_event_loop(web):
    # Aquecimento: a primeira request monta a pilha de middleware e importa módulos tardios, trabalho de uma vez só
    # que não é o que o teste mede. O bcrypt de produção custa ~0,2 s por login, bem acima do limite de 100 ms.
    assert (await _login(web, 1)).status_code == 200

    response, slow = await run_watched(lambda: _login(web))

    assert response.status_code == 200
    assert slow == []


async def test_ten_concurrent_logins_do_not_delay_the_health_check(web):
    """Mede o pior ciclo do prober (chamar /health + dormir 10 ms): um loop bloqueado atrasa o despertar do prober,
    não a duração da chamada em si."""
    worst = 0.0

    async def probe_health():
        nonlocal worst
        last = time.perf_counter()
        while True:
            response = await web.get("/health")
            assert response.status_code == 200
            await asyncio.sleep(0.01)
            now = time.perf_counter()
            worst = max(worst, now - last)
            last = now

    prober = asyncio.create_task(probe_health())
    await asyncio.sleep(0.05)  # o prober já mede antes dos logins
    try:
        responses = await asyncio.gather(*(_login(web, n) for n in range(10)))
    finally:
        prober.cancel()
        await asyncio.gather(prober, return_exceptions=True)

    assert [r.status_code for r in responses] == [200] * 10
    assert worst < HEALTH_CEILING_SECONDS
