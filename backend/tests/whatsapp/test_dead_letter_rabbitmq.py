"""Dead-letter, overflow e migração da fila de webhooks contra um RabbitMQ de verdade (marcador `rabbitmq`).

Só roda com `TEST_RABBITMQ_URL` (ex.: `amqp://usuario:senha@localhost:5672/`). Cada teste usa filas com nome único,
apagadas no fim; nunca toca em `webhooks.evolution`. No CI é o job `rabbitmq` do `backend.yml`.
"""
import asyncio
import json
import os
import uuid

import aio_pika
import pytest
import pytest_asyncio
from aiormq.exceptions import ChannelPreconditionFailed

from app.core.config import settings
from app.whatsapp import queue_admin
from app.whatsapp.message_queue import MessageQueueService, WebhookQueue

pytestmark = [pytest.mark.rabbitmq, pytest.mark.asyncio]


@pytest.fixture
def url(monkeypatch):
    url = os.environ["TEST_RABBITMQ_URL"]
    monkeypatch.setattr(settings, "RABBITMQ_URL", url)
    return url


@pytest_asyncio.fixture
async def connection(url):
    connection = await aio_pika.connect(url)
    yield connection
    await connection.close()


@pytest_asyncio.fixture
async def channel(connection):
    return await connection.channel(publisher_confirms=True)


def _topology(**limits) -> WebhookQueue:
    return WebhookQueue(f"test.{uuid.uuid4().hex[:10]}.webhooks", **limits)


@pytest_asyncio.fixture
async def cleanup(channel):
    topologies = []
    yield topologies.append
    for topology in topologies:
        for name in (topology.name, topology.dlq, f"{topology.name}.migrating"):
            await channel.queue_delete(name)
        await channel.exchange_delete(topology.dlx)


async def _wait_for(condition, timeout=10.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not await condition():
        assert asyncio.get_running_loop().time() < deadline, "condição não chegou a tempo"
        await asyncio.sleep(0.05)


async def _depths(topology, url):
    main, dlq = await queue_admin.status(topology, url)
    return main.messages, dlq.messages


async def _drain(channel, name):
    queue = await channel.declare_queue(name, passive=True)
    bodies = []
    while (message := await queue.get(no_ack=True, fail=False)) is not None:
        bodies.append(json.loads(message.body)["data"]["n"])
    return bodies


async def test_a_message_that_keeps_failing_ends_in_the_dead_letter_queue(url, channel, cleanup):
    topology = _topology()
    cleanup(topology)
    calls = []

    async def failing(_payload):
        calls.append(1)
        raise RuntimeError("venenosa")

    service = MessageQueueService(topology)
    service.register_consumer(failing)
    consuming = asyncio.create_task(service.start_consuming())
    try:
        assert await service.publish_webhook_event({"event": "messages.upsert", "n": 1})

        async def landed():
            return await _depths(topology, url) == (0, 1)

        await _wait_for(landed)
    finally:
        await service.stop_consuming()
        await consuming
        await service.disconnect()

    assert len(calls) == 2  # entrega original + a reentrega
    assert [item["event"] for item in await queue_admin.peek_dead_letters(5, topology, url)] == ["messages.upsert"]
    assert (await queue_admin.peek_dead_letters(5, topology, url))[0]["reason"] == "rejected"


async def test_overflow_sends_the_oldest_message_to_the_dead_letter_queue_and_keeps_accepting_new_ones(url, channel, cleanup):
    topology = _topology(max_length=2)
    cleanup(topology)
    service = MessageQueueService(topology)
    try:
        for n in (1, 2, 3):
            assert await service.publish_webhook_event({"event": "e", "n": n})
    finally:
        await service.disconnect()

    async def settled():
        return await _depths(topology, url) == (2, 1)

    await _wait_for(settled)
    assert (await queue_admin.peek_dead_letters(1, topology, url))[0]["reason"] == "maxlen"
    assert await _drain(channel, topology.dlq) == [1]
    assert await _drain(channel, topology.name) == [2, 3]


async def test_replay_returns_dead_letters_to_the_main_queue_in_order(url, channel, cleanup):
    topology = _topology()
    cleanup(topology)
    await topology.declare(channel)
    for n in (1, 2, 3):
        await channel.default_exchange.publish(
            aio_pika.Message(json.dumps({"data": {"n": n}}).encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=topology.dlq,
        )

    assert await queue_admin.replay_dead_letters(2, topology, url) == 2
    assert await _depths(topology, url) == (2, 1)
    assert await queue_admin.replay_dead_letters(None, topology, url) == 1
    assert await _drain(channel, topology.name) == [1, 2, 3]


async def test_migrating_a_queue_created_before_the_dead_letter_queue_keeps_every_message(
    url, connection, channel, cleanup
):
    topology = _topology()
    cleanup(topology)
    old_arguments = {"x-message-ttl": topology.ttl_ms, "x-max-length": topology.max_length}
    await channel.declare_queue(topology.name, durable=True, arguments=old_arguments)
    for n in (1, 2, 3):
        await channel.default_exchange.publish(
            aio_pika.Message(json.dumps({"data": {"n": n}}).encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=topology.name,
        )

    other = await connection.channel()  # o broker fecha o canal em que a declaração é recusada
    with pytest.raises(ChannelPreconditionFailed):
        await other.declare_queue(topology.name, durable=True, arguments=topology.arguments)

    result = await queue_admin.migrate(topology, url)

    assert (result.migrated, result.moved_out, result.moved_back) == (True, 3, 3)
    assert await _depths(topology, url) == (3, 0)
    assert await _drain(channel, topology.name) == [1, 2, 3]
    assert (await queue_admin.migrate(topology, url)).migrated is False

