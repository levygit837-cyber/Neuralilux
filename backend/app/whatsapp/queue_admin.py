"""Operação da fila de webhooks: situação, inspeção e reprocesso da DLQ, e migração de uma fila antiga.

Roda fora do worker (`scripts/queue_admin.py`), com a conexão própria de cada comando. Passo a passo para o
operador: `docs/operations.md`.

Toda mensagem movida entre filas só recebe `ack` na origem depois que o destino confirmou o publish
(`publisher_confirms`) e sem rota vira erro (`on_return_raises`): uma falha no meio duplica no máximo uma
mensagem, nunca perde. O consumer ignora a duplicata (dedup por `Message.message_id`).
"""
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractIncomingMessage, AbstractQueue
from aiormq.exceptions import ChannelNotFoundEntity, ChannelPreconditionFailed

from app.core.config import settings
from app.whatsapp.message_queue import WEBHOOKS, WebhookQueue


@dataclass(frozen=True)
class QueueDepth:
    name: str
    messages: Optional[int]  # None: a fila não existe
    consumers: Optional[int]


@dataclass(frozen=True)
class Migration:
    migrated: bool  # False: a fila já tinha os argumentos novos
    moved_out: int  # mensagens da fila antiga que passaram pela fila temporária
    moved_back: int  # mensagens devolvidas à fila nova (inclui as que sobraram de uma migração interrompida)


@asynccontextmanager
async def _connection(url: Optional[str] = None) -> AsyncIterator[AbstractConnection]:
    # Conexão simples, não robust: um canal fechado pelo broker (PRECONDITION_FAILED) fica fechado em vez de reabrir.
    connection = await aio_pika.connect(url or settings.RABBITMQ_URL)
    try:
        yield connection
    finally:
        await connection.close()


async def _channel(connection: AbstractConnection) -> AbstractChannel:
    return await connection.channel(publisher_confirms=True, on_return_raises=True)


async def _depth(connection: AbstractConnection, name: str) -> QueueDepth:
    """Mensagens e consumers de uma fila, sem criá-la; canal próprio porque o broker fecha o canal no 404."""
    channel = await connection.channel()
    try:
        queue = await channel.declare_queue(name, passive=True)
    except ChannelNotFoundEntity:
        return QueueDepth(name, None, None)
    result = queue.declaration_result
    await channel.close()
    return QueueDepth(name, result.message_count, result.consumer_count)


async def status(topology: WebhookQueue = WEBHOOKS, url: Optional[str] = None) -> List[QueueDepth]:
    async with _connection(url) as connection:
        return [await _depth(connection, name) for name in (topology.name, topology.dlq)]


def _copy(message: AbstractIncomingMessage) -> aio_pika.Message:
    """Cópia para republicar: mesmo corpo e propriedades, sem os cabeçalhos `x-*` que o broker acrescenta (`x-death`)."""
    headers = {key: value for key, value in (message.headers or {}).items() if not key.startswith("x-")}
    return aio_pika.Message(
        body=message.body,
        headers=headers,
        content_type=message.content_type,
        content_encoding=message.content_encoding,
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        message_id=message.message_id,
        timestamp=message.timestamp,
        type=message.type,
    )


async def _move(channel: AbstractChannel, source: AbstractQueue, destination: str, limit: Optional[int]) -> int:
    """Move até `limit` mensagens (todas, se None) de `source` para a fila `destination`, em ordem."""
    moved = 0
    while limit is None or moved < limit:
        message = await source.get(no_ack=False, fail=False)
        if message is None:
            break
        await channel.default_exchange.publish(_copy(message), routing_key=destination)
        await message.ack()
        moved += 1
    return moved


def _death_reason(message: AbstractIncomingMessage) -> Dict[str, Any]:
    """Por que o broker mandou a mensagem para a DLQ: `rejected` (consumer), `expired` (TTL) ou `maxlen`."""
    deaths = (message.headers or {}).get("x-death") or []
    first = deaths[0] if deaths else {}
    return {"reason": first.get("reason"), "from_queue": first.get("queue"), "count": first.get("count"),
            "died_at": str(first.get("time")) if first.get("time") else None}


def _summary(message: AbstractIncomingMessage) -> Dict[str, Any]:
    try:
        payload = json.loads(message.body)
        data = payload.get("data") or {}
        event: Dict[str, Any] = {"event": payload.get("event"), "instance": data.get("instance")}
    except (ValueError, AttributeError):
        event = {"event": None, "instance": None, "invalid_json": True}
    return {"message_id": message.message_id, "bytes": len(message.body), **event, **_death_reason(message)}


async def peek_dead_letters(limit: int = 10, topology: WebhookQueue = WEBHOOKS, url: Optional[str] = None) -> List[Dict[str, Any]]:
    """Resumo das primeiras `limit` mensagens da DLQ, sem tirá-las de lá."""
    async with _connection(url) as connection:
        channel = await _channel(connection)
        dlq = await channel.declare_queue(topology.dlq, passive=True)
        taken: List[AbstractIncomingMessage] = []
        while len(taken) < limit:
            message = await dlq.get(no_ack=False, fail=False)
            if message is None:
                break
            taken.append(message)
        summaries = [_summary(message) for message in taken]
        # Devolve só depois de ler todas: devolvida antes, a mesma mensagem voltaria na leitura seguinte.
        for message in reversed(taken):
            await message.reject(requeue=True)
        return summaries


async def replay_dead_letters(limit: Optional[int] = None, topology: WebhookQueue = WEBHOOKS, url: Optional[str] = None) -> int:
    """Devolve à fila principal até `limit` mensagens da DLQ (todas, se None). Devolve quantas moveu.

    Limitado ao que a DLQ tinha no início: se o worker rejeitar de novo uma mensagem reprocessada, ela volta para a
    DLQ e não entra num ciclo infinito dentro desta chamada.
    """
    async with _connection(url) as connection:
        channel = await _channel(connection)
        dlq = await channel.declare_queue(topology.dlq, passive=True)
        available = dlq.declaration_result.message_count
        return await _move(channel, dlq, topology.name, available if limit is None else min(limit, available))


async def _exists(connection: AbstractConnection, name: str) -> bool:
    return (await _depth(connection, name)).messages is not None


async def migrate(topology: WebhookQueue = WEBHOOKS, url: Optional[str] = None) -> Migration:
    """Leva a fila principal para os argumentos da topologia atual (DLX, overflow) sem perder mensagens.

    O broker recusa redeclarar uma fila com argumentos diferentes e não permite alterá-los, então a fila é
    recriada: as mensagens passam para `<fila>.migrating`, a fila antiga é apagada (só se vazia), a nova é
    declarada e as mensagens voltam em ordem. Rodar de novo é seguro: uma fila temporária que sobrou de uma
    execução interrompida é esvaziada na fila nova. Exige API e worker parados (docs/operations.md): um publish na
    janela entre apagar e declarar não tem rota.
    """
    temporary = f"{topology.name}.migrating"
    async with _connection(url) as connection:
        channel = await _channel(connection)
        await topology.declare_dead_letter(channel)

        # Redeclarar com os argumentos novos é o teste: passa se a fila não existe (e a cria já migrada) ou se já
        # está migrada; o broker recusa (e fecha o canal de teste) se ela tem os argumentos antigos.
        probe = await connection.channel()
        try:
            await probe.declare_queue(topology.name, durable=True, arguments=topology.arguments)
            needs_migration = False
            await probe.close()
        except ChannelPreconditionFailed:
            needs_migration = True

        moved_out = 0
        if needs_migration:
            old = await channel.declare_queue(topology.name, passive=True)
            await channel.declare_queue(temporary, durable=True)
            moved_out = await _move(channel, old, temporary, None)
            await old.delete(if_empty=True)  # falha se chegou mensagem no meio: fila com conteúdo nunca é apagada

        main = await topology.declare(channel)
        moved_back = 0
        if await _exists(connection, temporary):
            parked = await channel.declare_queue(temporary, durable=True)
            moved_back = await _move(channel, parked, main.name, None)
            await parked.delete(if_empty=True)
        return Migration(migrated=needs_migration, moved_out=moved_out, moved_back=moved_back)
