"""Intervalo mínimo entre reimportações do histórico da mesma Instance (#93): Redis `SET NX EX`, falha aberta."""
import time as real_time
from types import SimpleNamespace

import fakeredis
import pytest
import structlog

from app.core.config import settings
from app.whatsapp import reimport_guard

pytestmark = pytest.mark.asyncio

IGNORED = "History reimport ignored: the last one was less than the minimum interval ago"


class _Clock:
    """Relógio do fakeredis (ele expira chaves por `time.time()`): o teste avança o intervalo sem dormir."""

    def __init__(self):
        self.now = real_time.time()

    def time(self):
        return self.now

    def __getattr__(self, name):
        return getattr(real_time, name)


@pytest.fixture
def clock(monkeypatch):
    fake = _Clock()
    monkeypatch.setattr("fakeredis._socket._base.time", fake)
    return fake


@pytest.fixture(autouse=True)
def guard_up(monkeypatch):
    """Cada teste começa com o Redis tratado como no ar (o circuito é estado do módulo)."""
    monkeypatch.setattr(reimport_guard, "_down_until", 0.0)


@pytest.fixture
def redis_server(monkeypatch):
    """Um Redis em memória compartilhado: dois "workers" (dois clientes) enxergam as mesmas chaves."""
    monkeypatch.setattr(settings, "HISTORY_REIMPORT_MIN_INTERVAL_SECONDS", 300)
    monkeypatch.setattr(reimport_guard, "_redis", None)
    monkeypatch.setattr(reimport_guard, "_redis_loop", None)
    server = fakeredis.FakeServer()
    monkeypatch.setattr(
        reimport_guard, "Redis", type("R", (), {"from_url": staticmethod(lambda *a, **k: fakeredis.FakeAsyncRedis(server=server, decode_responses=True))})
    )
    return server


async def test_a_repeat_inside_the_interval_is_ignored_with_a_log(redis_server, clock):
    assert await reimport_guard.allow("inst-1", "chats.upsert") is True

    with structlog.testing.capture_logs() as logs:
        assert await reimport_guard.allow("inst-1", "connection.update") is False

    ignored = [log for log in logs if log["event"] == IGNORED]
    assert len(ignored) == 1
    assert ignored[0]["instance_id"] == "inst-1" and ignored[0]["reason"] == "connection.update"
    assert ignored[0]["min_interval_seconds"] == 300


async def test_the_interval_is_per_instance(redis_server, clock):
    assert await reimport_guard.allow("inst-1", "chats.upsert") is True
    assert await reimport_guard.allow("inst-2", "chats.upsert") is True
    assert await reimport_guard.allow("inst-1", "chats.upsert") is False


async def test_after_the_interval_the_instance_can_be_reimported(redis_server, clock):
    assert await reimport_guard.allow("inst-1", "chats.upsert") is True
    clock.now += 299
    assert await reimport_guard.allow("inst-1", "chats.upsert") is False
    clock.now += 2
    assert await reimport_guard.allow("inst-1", "chats.upsert") is True


async def test_two_workers_share_the_interval(redis_server, clock, monkeypatch):
    """Multi-worker: a chave está no Redis, não na memória do processo. Só um dos dois importa."""
    assert await reimport_guard.allow("inst-1", "chats.upsert") is True
    monkeypatch.setattr(reimport_guard, "_redis", None)  # outro processo: cliente próprio, mesmo Redis
    monkeypatch.setattr(reimport_guard, "_redis_loop", None)
    assert await reimport_guard.allow("inst-1", "chats.upsert") is False


async def test_interval_zero_turns_the_guard_off(redis_server, clock, monkeypatch):
    monkeypatch.setattr(settings, "HISTORY_REIMPORT_MIN_INTERVAL_SECONDS", 0)
    assert [await reimport_guard.allow("inst-1", "chats.upsert") for _ in range(3)] == [True, True, True]


async def test_redis_down_fails_open_and_reconnects_next_time(monkeypatch, clock):
    monkeypatch.setattr(settings, "HISTORY_REIMPORT_MIN_INTERVAL_SECONDS", 300)
    monkeypatch.setattr(reimport_guard, "_redis", None)
    monkeypatch.setattr(reimport_guard, "_redis_loop", None)
    monotonic = {"now": 1000.0}
    monkeypatch.setattr(reimport_guard, "time", SimpleNamespace(monotonic=lambda: monotonic["now"]))

    class Down:
        async def set(self, *args, **kwargs):
            raise ConnectionError("redis fora do ar")

        async def aclose(self):
            pass

    healthy = fakeredis.FakeAsyncRedis(server=fakeredis.FakeServer(), decode_responses=True)
    clients = iter([Down(), healthy])
    monkeypatch.setattr(reimport_guard, "Redis", type("R", (), {"from_url": staticmethod(lambda *a, **k: next(clients))}))

    with structlog.testing.capture_logs() as logs:
        assert await reimport_guard.allow("inst-1", "chats.upsert") is True  # Redis fora: reimporta

    assert [log["event"] for log in logs] == ["History reimport guard unavailable; importing anyway"]
    assert [(log["log_level"], bool(log["exc_info"])) for log in logs] == [("warning", True)]
    assert "error" not in logs[0]
    monotonic["now"] += reimport_guard.DOWN_BACKOFF_SECONDS
    assert await reimport_guard.allow("inst-1", "chats.upsert") is True  # cliente novo, chave criada
    assert await reimport_guard.allow("inst-1", "chats.upsert") is False


async def test_after_a_failure_events_inside_the_backoff_skip_redis_and_import(monkeypatch, clock):
    """Redis fora do ar não cobra os timeouts (até 4 s) de cada evento do webhook: dentro do backoff, nem tenta."""
    monkeypatch.setattr(settings, "HISTORY_REIMPORT_MIN_INTERVAL_SECONDS", 300)
    monkeypatch.setattr(reimport_guard, "_redis", None)
    monkeypatch.setattr(reimport_guard, "_redis_loop", None)
    monotonic = {"now": 1000.0}
    monkeypatch.setattr(reimport_guard, "time", SimpleNamespace(monotonic=lambda: monotonic["now"]))
    attempts = []

    class Down:
        async def set(self, *args, **kwargs):
            attempts.append(monotonic["now"])
            raise ConnectionError("redis fora do ar")

        async def aclose(self):
            pass

    monkeypatch.setattr(reimport_guard, "Redis", type("R", (), {"from_url": staticmethod(lambda *a, **k: Down())}))

    assert [await reimport_guard.allow("inst-1", "chats.upsert") for _ in range(3)] == [True, True, True]
    assert attempts == [1000.0]  # só a primeira falha tocou o Redis

    monotonic["now"] += reimport_guard.DOWN_BACKOFF_SECONDS
    assert await reimport_guard.allow("inst-1", "chats.upsert") is True
    assert attempts == [1000.0, 1005.0]  # passado o backoff, tenta de novo
