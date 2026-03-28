"""
Socket.IO client that consumes realtime events from Evolution API and
forwards them to the existing webhook queue flow.
"""

from __future__ import annotations

from typing import Any

import aiohttp
import socketio
import structlog

from app.core.config import settings
from app.services.message_queue_service import message_queue_service

logger = structlog.get_logger()


def _ensure_aiohttp_ws_timeout_compat() -> None:
    """Bridge python-engineio's newer timeout API to the aiohttp version in use."""
    if hasattr(aiohttp, "ClientWSTimeout"):
        return

    def _client_ws_timeout(*, ws_close: float | None = None, **_: Any) -> float:
        return float(ws_close or 10)

    aiohttp.ClientWSTimeout = _client_ws_timeout  # type: ignore[attr-defined]


class EvolutionRealtimeService:
    SUPPORTED_EVENTS = (
        "messages.upsert",
        "messages.update",
        "connection.update",
        "qrcode.updated",
    )

    def __init__(self) -> None:
        _ensure_aiohttp_ws_timeout_compat()
        self._client = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=0,
            logger=False,
            engineio_logger=False,
        )
        self._connected = False
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self._client.event
        async def connect():
            self._connected = True
            logger.info("Connected to Evolution realtime socket")

        @self._client.event
        async def disconnect():
            self._connected = False
            logger.warning("Disconnected from Evolution realtime socket")

        @self._client.event
        async def connect_error(data):
            logger.error("Evolution realtime socket connection error", data=data)

        for event_name in self.SUPPORTED_EVENTS:
            self._client.on(event_name, self._build_event_handler(event_name))

    def _build_event_handler(self, event_name: str):
        async def handler(payload: dict[str, Any]) -> None:
            await self._forward_event(event_name, payload)

        return handler

    async def start(self) -> None:
        if not settings.EVOLUTION_WEBSOCKET_ENABLED or self._connected:
            return

        await self._client.connect(
            settings.EVOLUTION_API_URL,
            headers={"apikey": settings.EVOLUTION_API_KEY},
            transports=["websocket", "polling"],
            wait_timeout=10,
        )

    async def stop(self) -> None:
        if self._client.connected:
            await self._client.disconnect()
        self._connected = False

    async def _forward_event(self, event_name: str, payload: dict[str, Any]) -> None:
        normalized_payload = {
            **payload,
            "event": event_name,
            "source": "websocket",
        }
        message_queue_service.publish_webhook_event(normalized_payload)


evolution_realtime_service = EvolutionRealtimeService()
