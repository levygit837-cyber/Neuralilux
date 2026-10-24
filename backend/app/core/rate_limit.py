"""Rate limit por IP das rotas públicas (/auth/login e /auth/register), em janela fixa no Redis.

- Cada tentativa conta, acertando ou errando. Acima do limite a resposta é 429 com `Retry-After` (segundos até a
  janela virar).
- Redis fora do ar (ou mais lento que os timeouts do cliente): **falha fechada**, 503. Quem não consegue contar
  tentativas não pode deixar o login aberto a força bruta. O custo é o login indisponível enquanto o Redis cai, o
  que já derruba o resto do atendimento (event bus, debounce).
- IP do cliente: o do peer TCP. `X-Forwarded-For` (todas as linhas do cabeçalho) só é lido quando o peer está em
  `TRUSTED_PROXIES`. IPv6 conta por prefixo /64.
"""
from __future__ import annotations

import asyncio
import ipaddress
from typing import Optional

import structlog
from fastapi import HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.core.config import settings

logger = structlog.get_logger()

_KEY_PREFIX = "neuralilux:ratelimit"

_redis: Optional[Redis] = None
_redis_loop: Optional[asyncio.AbstractEventLoop] = None
_closing: set[asyncio.Task] = set()  # fechamentos de clientes descartados, em background


def _new_client() -> Redis:
    """Cliente com os mesmos timeouts do event bus: Redis travado vira erro, não espera infinita."""
    return Redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
        health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL_SECONDS,
    )


def _client() -> Redis:
    """O cliente Redis fica preso ao event loop que o criou; outro loop recebe um cliente novo."""
    global _redis, _redis_loop
    loop = asyncio.get_running_loop()
    if _redis is None or _redis_loop is not loop:
        _redis = _new_client()
        _redis_loop = loop
    return _redis


async def _close_quietly(client: Redis) -> None:
    try:
        await asyncio.wait_for(client.aclose(), timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS)
    except Exception:
        pass


def _discard_client() -> None:
    """Descarta o cliente depois de uma falha (a próxima tentativa reconecta do zero) e o fecha em background.

    Sem o `aclose()`, cada falha com o Redis fora do ar deixaria um pool de conexões aberto. Um cliente de outro
    loop não é fechado: o `aclose()` falharia no loop morto (mesma regra do event bus).
    """
    global _redis, _redis_loop
    client, loop = _redis, _redis_loop
    _redis = None
    _redis_loop = None
    if client is None or loop is not asyncio.get_running_loop():
        return
    task = asyncio.create_task(_close_quietly(client))
    _closing.add(task)  # referência forte: o loop só guarda referência fraca da task
    task.add_done_callback(_closing.discard)


def _trusted_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    return [ipaddress.ip_network(entry, strict=False) for entry in settings.TRUSTED_PROXIES]


def _is_trusted(host: str, networks: list) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in networks)


def client_ip(request: Request) -> str:
    """IP do cliente: o peer TCP, ou, se o peer é um proxy confiável, o último endereço não confiável do
    `X-Forwarded-For` (da direita para a esquerda, pulando os proxies confiáveis).

    Um valor que não é IP no cabeçalho nunca vira chave: volta o IP do peer.
    """
    peer = request.client.host if request.client else "unknown"
    networks = _trusted_networks()
    if not networks or not _is_trusted(peer, networks):
        return peer
    # `getlist`: o proxy pode mandar o cabeçalho em várias linhas (o HAProxy anexa uma linha nova por padrão), e
    # `get` leria só a primeira, que é a do cliente.
    forwarded = [
        part.strip()
        for line in request.headers.getlist("x-forwarded-for")
        for part in line.split(",")
        if part.strip()
    ]
    for hop in reversed(forwarded):
        try:
            address = ipaddress.ip_address(hop)
        except ValueError:
            return peer
        if not _is_trusted(hop, networks):
            return str(address)
    return str(ipaddress.ip_address(forwarded[0])) if forwarded else peer


def _bucket(ip: str) -> str:
    """Chave do contador: IPv4 como está; IPv6 pelo prefixo /64, porque um cliente recebe um /64 inteiro (ou mais)
    e trocar o sufixo daria bilhões de contadores novos. IPv4 mapeado em IPv6 vira o IPv4."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.IPv6Network((address, 64), strict=False))
    return ip


async def _hit(key: str, window_seconds: int) -> tuple[int, int]:
    """Conta uma tentativa na janela de `key`. Devolve (tentativas na janela, segundos até a janela virar)."""
    timeout = settings.REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS + settings.REDIS_SOCKET_TIMEOUT_SECONDS
    async with _client().pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)  # só a primeira tentativa da janela arma o relógio
        pipe.ttl(key)
        count, _, ttl = await asyncio.wait_for(pipe.execute(), timeout=timeout)
    return int(count), max(int(ttl), 1)


async def enforce_rate_limit(request: Request, scope: str, attempts: int, window_seconds: int) -> None:
    """Conta a tentativa deste IP em `scope`. 429 + Retry-After acima de `attempts` na janela; 503 se o Redis falha."""
    ip = client_ip(request)
    try:
        count, retry_after = await _hit(f"{_KEY_PREFIX}:{scope}:{_bucket(ip)}", window_seconds)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # inclui TimeoutError do teto
        _discard_client()
        if isinstance(exc, ResponseError):
            reason = "Redis rejected the rate limit command (EXPIRE NX needs Redis >= 7.0)"
        else:
            reason = "Redis unavailable or too slow"
        logger.exception(
            f"Rate limit failed closed: {reason}; refusing the request",
            scope=scope,
            error_type=type(exc).__name__,
        )
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service temporarily unavailable")
    if count > attempts:
        logger.warning("Rate limit exceeded", scope=scope, ip=ip, attempts=count)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts, try again later",
            headers={"Retry-After": str(retry_after)},
        )


async def limit_login(request: Request) -> None:
    await enforce_rate_limit(
        request, "login", settings.LOGIN_RATE_LIMIT_ATTEMPTS, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    )


async def limit_register(request: Request) -> None:
    await enforce_rate_limit(
        request, "register", settings.REGISTER_RATE_LIMIT_ATTEMPTS, settings.REGISTER_RATE_LIMIT_WINDOW_SECONDS
    )
