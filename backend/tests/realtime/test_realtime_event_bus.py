"""O bus publica no Redis a partir de qualquer event loop, sem reaproveitar cliente de loop fechado."""
import asyncio

import structlog

from app.realtime import event_bus as bus_module
from app.realtime.event_bus import RealtimeEventBus


class LoopBoundRedis:
    """Imita o redis.asyncio: usar o cliente fora do loop que o criou falha como em produção."""

    created: list["LoopBoundRedis"] = []

    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self.published = []
        LoopBoundRedis.created.append(self)

    @classmethod
    def from_url(cls, *_args, **_kwargs):
        return cls()

    async def publish(self, channel, payload):
        if asyncio.get_running_loop() is not self.loop:
            raise RuntimeError("Event loop is closed")
        self.published.append((channel, payload))

    async def aclose(self):
        pass


def _bus(monkeypatch) -> RealtimeEventBus:
    LoopBoundRedis.created = []
    monkeypatch.setattr(bus_module, "Redis", LoopBoundRedis)
    return RealtimeEventBus()


def test_publish_after_the_previous_loop_was_closed_uses_a_fresh_client(monkeypatch):
    bus = _bus(monkeypatch)

    asyncio.run(bus.publish({"type": "a"}))  # asyncio.run fecha o loop ao terminar
    asyncio.run(bus.publish({"type": "b"}))

    assert len(LoopBoundRedis.created) == 2
    assert [len(client.published) for client in LoopBoundRedis.created] == [1, 1]


def test_publishes_in_the_same_loop_share_one_client(monkeypatch):
    bus = _bus(monkeypatch)

    async def publish_twice():
        await bus.publish({"type": "a"})
        await bus.publish({"type": "b"})

    asyncio.run(publish_twice())

    assert len(LoopBoundRedis.created) == 1
    assert len(LoopBoundRedis.created[0].published) == 2


# --- Redis que não responde: o evento é perdido, nunca o Turn -------------------------------------


class HangingRedis(LoopBoundRedis):
    async def publish(self, channel, payload):
        await asyncio.Event().wait()


class FailingRedis(LoopBoundRedis):
    async def publish(self, channel, payload):
        raise ConnectionError("redis fora")


def _bus_with(monkeypatch, redis_class, **settings_override) -> RealtimeEventBus:
    LoopBoundRedis.created = []
    monkeypatch.setattr(bus_module, "Redis", redis_class)
    for name, value in settings_override.items():
        monkeypatch.setattr(bus_module.settings, name, value)
    return RealtimeEventBus()


def test_hanging_redis_releases_the_caller_within_the_ceiling_and_logs_the_lost_event(monkeypatch):
    bus = _bus_with(monkeypatch, HangingRedis, REALTIME_PUBLISH_TIMEOUT_SECONDS=0.05)

    async def run():
        started = asyncio.get_running_loop().time()
        await bus.publish({"type": "thinking"})
        return asyncio.get_running_loop().time() - started

    with structlog.testing.capture_logs() as logs:
        elapsed = asyncio.run(run())

    assert elapsed < 1
    assert [log["event_type"] for log in logs if log["event"].startswith("Realtime event dropped")] == ["thinking"]


def test_after_a_failure_events_are_dropped_without_waiting_until_the_cooldown_ends(monkeypatch):
    bus = _bus_with(monkeypatch, HangingRedis, REALTIME_PUBLISH_TIMEOUT_SECONDS=0.05, REALTIME_PUBLISH_COOLDOWN_SECONDS=60)

    async def run():
        await bus.publish({"type": "a"})
        loop = asyncio.get_running_loop()
        started = loop.time()
        for _ in range(20):
            await bus.publish({"type": "b"})
        return loop.time() - started

    assert asyncio.run(run()) < 0.05  # 20 eventos x 0,05 s se cada um esperasse o teto
    assert len(LoopBoundRedis.created) == 1  # só o primeiro chegou a tentar


def test_bus_reconnects_with_a_fresh_client_after_the_cooldown(monkeypatch):
    bus = _bus_with(monkeypatch, FailingRedis, REALTIME_PUBLISH_COOLDOWN_SECONDS=0)

    async def run():
        await bus.publish({"type": "a"})
        monkeypatch.setattr(bus_module, "Redis", LoopBoundRedis)  # o Redis voltou
        await bus.publish({"type": "b"})

    asyncio.run(run())

    assert [type(client) for client in LoopBoundRedis.created] == [FailingRedis, LoopBoundRedis]
    assert len(LoopBoundRedis.created[1].published) == 1


def test_client_is_created_with_timeouts_and_health_check(monkeypatch):
    captured = {}

    class Capturing(LoopBoundRedis):
        @classmethod
        def from_url(cls, _url, **kwargs):
            captured.update(kwargs)
            return cls()

    bus = _bus_with(monkeypatch, Capturing)
    asyncio.run(bus.publish({"type": "a"}))

    assert captured["socket_connect_timeout"] > 0
    assert captured["socket_timeout"] > 0
    assert captured["health_check_interval"] > 0


def test_closing_a_hung_client_does_not_add_to_the_callers_wait(monkeypatch):
    class HangsOnClose(HangingRedis):
        async def aclose(self):
            await asyncio.Event().wait()

    bus = _bus_with(monkeypatch, HangsOnClose, REALTIME_PUBLISH_TIMEOUT_SECONDS=0.1)

    async def run():
        loop = asyncio.get_running_loop()
        started = loop.time()
        await bus.publish({"type": "a"})
        elapsed = loop.time() - started
        await bus.stop()  # espera o fechamento em background, que também tem teto
        return elapsed

    assert asyncio.run(run()) < 0.15  # teto de 0,1 s; somar o aclose() daria ~0,2 s


def test_cooldown_not_greater_than_the_publish_timeout_is_refused():
    import pytest

    from app.core.config import Settings

    with pytest.raises(ValueError, match="REALTIME_PUBLISH_COOLDOWN_SECONDS"):
        Settings(_env_file=None, REALTIME_PUBLISH_TIMEOUT_SECONDS=2, REALTIME_PUBLISH_COOLDOWN_SECONDS=2)
