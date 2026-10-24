"""Intervalo mínimo entre reimportações do histórico de uma Instance.

`chats.upsert` e `connection.update` com `open` disparam a importação (`history_sync`), e a Evolution repete os dois
com frequência (reconexões, rajadas de chats). Cada importação lê o histórico inteiro, então uma repetição dentro de
`HISTORY_REIMPORT_MIN_INTERVAL_SECONDS` é ignorada, com log.

- Redis `SET NX EX`: uma chave por Instance, com TTL igual ao intervalo. Quem cria a chave importa; quem não cria
  ignora. É atômico e compartilhado, então vale entre todos os workers: com N workers, uma reimportação por
  intervalo no total, não uma por worker. O estado em memória do processo não serviria, pois cada worker teria o
  seu relógio.
- Redis fora do ar (ou mais lento que os timeouts do cliente): **falha aberta**, reimporta, e lembra a falha por
  `DOWN_BACKOFF_SECONDS`: nesse tempo os eventos seguintes reimportam direto, sem pagar de novo os timeouts (até 4 s
  por evento, no handler do webhook). O oposto do rate limit de login: aqui perder a importação deixaria a Instance
  sem histórico, e importar demais custa só tempo, porque a importação é idempotente (`message_id`) e uma por vez
  por Instance (advisory lock no Postgres).
- Intervalo 0 desliga o guarda: toda ocorrência importa.
- A chave é gravada ao decidir, não ao terminar: uma importação que falha também espera o intervalo.
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

import structlog
from redis.asyncio import Redis

from app.core.config import settings

logger = structlog.get_logger()

_KEY_PREFIX = "neuralilux:history_reimport"
DOWN_BACKOFF_SECONDS = 5.0

_redis: Optional[Redis] = None
_redis_loop: Optional[asyncio.AbstractEventLoop] = None
_down_until = 0.0  # `time.monotonic()` até quando o Redis é tratado como fora do ar (falha aberta sem tentar)


def _client() -> Redis:
    """O cliente Redis fica preso ao event loop que o criou; outro loop recebe um cliente novo."""
    global _redis, _redis_loop
    loop = asyncio.get_running_loop()
    if _redis is None or _redis_loop is not loop:
        _redis = Redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS,
        )
        _redis_loop = loop
    return _redis


async def close() -> None:
    """Fecha o cliente deste loop (shutdown da API e do worker). Idempotente."""
    global _redis, _redis_loop
    client, loop = _redis, _redis_loop
    _redis = None
    _redis_loop = None
    if client is not None and loop is asyncio.get_running_loop():
        try:
            await asyncio.wait_for(client.aclose(), timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS)
        except Exception as exc:
            logger.debug("History reimport guard: closing the Redis client failed", error_type=type(exc).__name__)


async def allow(instance_id: str, reason: str) -> bool:
    """True se a Instance pode ser reimportada agora; False (com log) se a última decisão foi há menos que o intervalo.

    `reason` é o gatilho (`chats.upsert` ou `connection.update`) e só aparece no log.
    """
    interval = settings.HISTORY_REIMPORT_MIN_INTERVAL_SECONDS
    if interval <= 0:
        return True
    global _down_until
    if time.monotonic() < _down_until:  # Redis caiu há pouco: não paga os timeouts de novo a cada evento
        return True
    timeout = settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS + settings.REDIS_SOCKET_TIMEOUT_SECONDS
    try:
        acquired = await asyncio.wait_for(
            _client().set(f"{_KEY_PREFIX}:{instance_id}", reason, nx=True, ex=interval), timeout=timeout
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # inclui TimeoutError do teto
        _down_until = time.monotonic() + DOWN_BACKOFF_SECONDS
        await close()  # a próxima tentativa reconecta do zero
        logger.warning(
            "History reimport guard unavailable; importing anyway",
            instance_id=instance_id,
            reason=reason,
            error_type=type(exc).__name__,
            exc_info=True,
        )
        return True
    if not acquired:
        logger.info(
            "History reimport ignored: the last one was less than the minimum interval ago",
            instance_id=instance_id,
            reason=reason,
            min_interval_seconds=interval,
        )
        return False
    return True
