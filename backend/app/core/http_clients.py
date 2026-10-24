"""Um `httpx.AsyncClient` por destino HTTP, vivo durante o processo (API e worker).

Antes, cada chamada abria e fechava o próprio cliente: handshake TCP/TLS a cada request, inclusive no "digitando…".
Agora o pool de conexões (keep-alive) é reaproveitado. Os destinos são a Evolution (um) e cada Gateway (pela raiz
da URL; vêm do banco, então o cliente nasce na primeira chamada).

- O timeout vai em cada request (`client.request(..., timeout=...)`), não no cliente: o destino é um só, os prazos
  variam por chamada.
- Ciclo de vida: a API chama `close_all()` no fim do `lifespan` e o worker no `finally` de `run()`.
- O cliente fica preso ao event loop que o criou. Outro loop (só acontece nos testes, um loop por teste) recebe um
  cliente novo; o antigo é descartado sem `aclose()`, que falharia no loop morto.
"""
from __future__ import annotations

import asyncio

import httpx

_clients: dict[str, tuple[httpx.AsyncClient, asyncio.AbstractEventLoop]] = {}


def get(destination: str) -> httpx.AsyncClient:
    """O cliente do destino (ex.: `evolution:http://host:8081`); cria na primeira chamada."""
    loop = asyncio.get_running_loop()
    entry = _clients.get(destination)
    if entry is None or entry[1] is not loop:
        entry = _clients[destination] = (httpx.AsyncClient(), loop)
    return entry[0]


async def close_all() -> None:
    """Fecha os clientes deste loop e esquece todos. Idempotente."""
    loop = asyncio.get_running_loop()
    entries = list(_clients.values())
    _clients.clear()
    for client, owner in entries:
        if owner is loop:
            await client.aclose()
