"""
Redis-backed event bus used to move realtime UI events from the worker
process to the API process.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable, Optional

import structlog
from redis.asyncio import Redis

from app.core.config import settings

logger = structlog.get_logger()


class RealtimeEventBus:
    def __init__(self) -> None:
        self._redis: Optional[Redis] = None
        self._pubsub = None
        self._listener_task: Optional[asyncio.Task] = None

    async def _get_redis(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def publish(self, event: dict[str, Any]) -> None:
        redis = Redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        try:
            await redis.publish(settings.REALTIME_REDIS_CHANNEL, json.dumps(event, default=str))
        finally:
            await redis.aclose()

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
                message = await self._pubsub.get_message(timeout=1.0)
                if message and message.get("type") == "message":
                    payload = json.loads(message["data"])
                    await handler(payload)
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive logging path
                logger.error("Realtime event bus listener error", error=str(exc))
                await asyncio.sleep(1)

    async def stop(self) -> None:
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

        if self._redis:
            await self._redis.aclose()
            self._redis = None


realtime_event_bus = RealtimeEventBus()
