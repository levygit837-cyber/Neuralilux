"""
Redis-backed event bus used to move realtime UI events from the worker
process to the API process.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Awaitable, Callable, Optional

import structlog
from redis.asyncio import Redis

from app.core.config import settings

logger = structlog.get_logger()


def _new_client() -> Redis:
    """Cliente com timeouts de conexão e de operação e health check: Redis travado vira erro, não espera infinita."""
    return Redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
        health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS,
    )


class RealtimeEventBus:
    def __init__(self) -> None:
        self._unavailable_until = 0.0
        self._closing: set[asyncio.Task] = set()  # fechamentos de clientes descartados, em background
        self._redis: Optional[Redis] = None
        self._pub_redis: Optional[Redis] = None
        self._pub_loop: Optional[asyncio.AbstractEventLoop] = None
        self._pubsub = None
        self._listener_task: Optional[asyncio.Task] = None

    async def _get_redis(self) -> Redis:
        if self._redis is None:
            self._redis = _new_client()
        return self._redis

    async def publish(self, event: dict[str, Any]) -> None:
        """Publica um evento de UI sem nunca segurar nem derrubar quem chamou.

        Evento de UI roda dentro do Turn e do lock da Conversation: falha ou lentidão do Redis
        só perde o evento (logado). O teto de quem chama é REALTIME_PUBLISH_TIMEOUT_SECONDS: o
        fechamento do cliente descartado roda em background. Depois de uma falha o bus pula os
        publishes por REALTIME_PUBLISH_COOLDOWN_SECONDS e recria o cliente, para que uma sequência
        de eventos do mesmo Turn não pague o teto a cada um.
        """
        if time.monotonic() < self._unavailable_until:
            logger.warning("Realtime event dropped: Redis unavailable", event_type=event.get("type"))
            return
        try:
            await asyncio.wait_for(self._publish(event), timeout=settings.REALTIME_PUBLISH_TIMEOUT_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:  # inclui TimeoutError do teto
            self._unavailable_until = time.monotonic() + settings.REALTIME_PUBLISH_COOLDOWN_SECONDS
            logger.warning(
                "Realtime event dropped: Redis publish failed",
                event_type=event.get("type"),
                exc_info=True,
            )
            self._discard_publisher()

    async def _publish(self, event: dict[str, Any]) -> None:
        # O cliente Redis fica preso ao event loop que o criou. Um cliente de outro loop (já fechado)
        # é descartado sem aclose(), que falharia no loop morto, e um novo é criado neste.
        loop = asyncio.get_running_loop()
        if self._pub_redis is None or self._pub_loop is not loop:
            self._pub_redis = _new_client()
            self._pub_loop = loop
        await self._pub_redis.publish(
            settings.REALTIME_REDIS_CHANNEL,
            json.dumps(event, default=str),
        )

    def _discard_publisher(self) -> None:
        """Descarta o cliente de publish (a próxima tentativa reconecta do zero) e o fecha em background."""
        client, loop = self._pub_redis, self._pub_loop
        self._pub_redis = None
        self._pub_loop = None
        if client is None or loop is not asyncio.get_running_loop():
            return
        task = asyncio.create_task(self._close_quietly(client))
        self._closing.add(task)  # referência forte: o loop só guarda referência fraca da task
        task.add_done_callback(self._closing.discard)

    @staticmethod
    async def _close_quietly(client: Redis) -> None:
        try:
            await asyncio.wait_for(client.aclose(), timeout=settings.REALTIME_PUBLISH_TIMEOUT_SECONDS)
        except Exception:
            pass

    async def start(
        self,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if self._listener_task and not self._listener_task.done():
            return

        redis = await self._get_redis()
        self._pubsub = redis.pubsub(ignore_subscribe_messages=True)
        await self._pubsub.subscribe(settings.REALTIME_REDIS_CHANNEL)
        self._listener_task = asyncio.create_task(self._listen(handler))
        logger.info("Realtime event bus listener started", channel=settings.REALTIME_REDIS_CHANNEL)

    async def _listen(
        self,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        assert self._pubsub is not None

        while True:
            try:
                message = await self._pubsub.get_message(timeout=0.1)
                if message and message.get("type") == "message":
                    payload = json.loads(message["data"])
                    await handler(payload)
                else:
                    await asyncio.sleep(0.005)
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - defensive logging path
                logger.exception("Realtime event bus listener error")
                await asyncio.sleep(1)

    async def stop(self) -> None:
        if self._closing:
            await asyncio.gather(*self._closing, return_exceptions=True)

        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

        if self._pubsub:
            await self._pubsub.unsubscribe(settings.REALTIME_REDIS_CHANNEL)
            await self._pubsub.close()
            self._pubsub = None

        if self._pub_redis:
            if self._pub_loop is asyncio.get_running_loop():
                await self._pub_redis.aclose()
            self._pub_redis = None
            self._pub_loop = None

        if self._redis:
            await self._redis.aclose()
            self._redis = None


realtime_event_bus = RealtimeEventBus()
