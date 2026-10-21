"""O bus publica no Redis a partir de qualquer event loop, sem reaproveitar cliente de loop fechado."""
import asyncio

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
