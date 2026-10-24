"""Dead-letter, overflow, migração e rollback da fila de webhooks contra um RabbitMQ de verdade (marcador `rabbitmq`).

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
        for name in (topology.name, topology.dlq, f"{topology.name}.migrating", f"{topology.name}.rollingback"):
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



async def _publish(channel, queue, numbers):
    for n in numbers:
        await channel.default_exchange.publish(
            aio_pika.Message(
                json.dumps({"data": {"n": n}}).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=f"id-{n}",
            ),
            routing_key=queue,
        )


async def _declare_old(channel, topology):
    return await channel.declare_queue(topology.name, durable=True, arguments=topology.legacy_arguments)


async def _is_refused(connection, topology, arguments):
    other = await connection.channel()  # o broker fecha o canal em que a declaração é recusada
    try:
        await other.declare_queue(topology.name, durable=True, arguments=arguments)
    except ChannelPreconditionFailed:
        return True
    await other.close()
    return False


async def test_rollback_after_migrate_restores_the_old_queue_without_losing_or_reordering_messages(
    url, connection, channel, cleanup
):
    topology = _topology()
    cleanup(topology)
    await _declare_old(channel, topology)
    await _publish(channel, topology.name, (1, 2, 3))

    assert (await queue_admin.migrate(topology, url)).migrated is True
    assert await _is_refused(connection, topology, topology.legacy_arguments)  # o código antigo não sobe
    result = await queue_admin.rollback(topology, url)

    assert (result.rolled_back, result.moved_out, result.moved_back) == (True, 3, 3)
    assert not await _is_refused(connection, topology, topology.legacy_arguments)  # o código antigo volta a declarar
    assert await _is_refused(connection, topology, topology.arguments)
    assert await _depths(topology, url) == (3, 0)
    queue = await channel.declare_queue(topology.name, passive=True)
    first = await queue.get(no_ack=True)
    assert first.message_id == "id-1"  # as propriedades sobrevivem à ida e volta
    assert [json.loads(first.body)["data"]["n"]] + await _drain(channel, topology.name) == [1, 2, 3]
    assert (await queue_admin.rollback(topology, url)).rolled_back is False  # idempotente


async def test_rollback_resumes_from_the_temporary_queue_left_by_an_interrupted_run(url, connection, channel, cleanup):
    topology = _topology()
    cleanup(topology)
    await _declare_old(channel, topology)  # a fila já foi apagada e recriada com os argumentos antigos
    temporary = f"{topology.name}.rollingback"
    await channel.declare_queue(temporary, durable=True)
    await _publish(channel, temporary, (1, 2))  # sobrou a temporária da execução interrompida

    result = await queue_admin.rollback(topology, url)

    assert (result.rolled_back, result.moved_out, result.moved_back) == (False, 0, 2)
    assert await _drain(channel, topology.name) == [1, 2]
    assert await queue_admin._exists(connection, temporary) is False


async def test_rollback_refuses_while_the_dead_letter_queue_has_messages(url, connection, channel, cleanup):
    topology = _topology()
    cleanup(topology)
    await topology.declare(channel)
    await _publish(channel, topology.name, (1,))
    await _publish(channel, topology.dlq, (2,))

    with pytest.raises(queue_admin.QueueAdminError, match="replay"):
        await queue_admin.rollback(topology, url)

    assert await _depths(topology, url) == (1, 1)  # nada foi movido
    assert await _is_refused(connection, topology, topology.legacy_arguments)

    assert await queue_admin.replay_dead_letters(None, topology, url) == 1
    assert (await queue_admin.rollback(topology, url)).rolled_back is True
    assert await _drain(channel, topology.name) == [1, 2]


async def _ready(topology, url, expected):
    return (await _depths(topology, url))[0] == expected


@pytest.mark.parametrize("operation", ["migrate", "rollback"])
async def test_migrate_and_rollback_refuse_while_the_queue_has_a_consumer(
    operation, url, connection, channel, cleanup
):
    topology = _topology()
    cleanup(topology)
    if operation == "migrate":
        queue = await _declare_old(channel, topology)
        await topology.declare_dead_letter(channel)
    else:
        queue = await topology.declare(channel)
    await _publish(channel, topology.name, (1, 2))

    async def hold(_message):
        return None  # nunca dá ack: a mensagem fica entregue ao consumer

    consumer_channel = await connection.channel()
    consuming = await consumer_channel.declare_queue(topology.name, passive=True)
    await consuming.consume(hold, no_ack=False)

    with pytest.raises(queue_admin.QueueAdminError, match="consumer"):
        await getattr(queue_admin, operation)(topology, url)

    await consumer_channel.close()  # o broker devolve à fila as mensagens entregues e sem ack
    await _wait_for(lambda: _ready(topology, url, 2))
    assert await _is_refused(connection, topology, topology.arguments if operation == "rollback" else topology.legacy_arguments) is False
