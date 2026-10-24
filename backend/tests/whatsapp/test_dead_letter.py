"""Dead-letter da fila de webhooks, com um broker simulado: quem falha de novo vai para a DLQ, e o payload sai em JSON.

O comportamento no RabbitMQ de verdade (DLX, overflow, migração) está em `test_dead_letter_rabbitmq.py`.
"""
import base64
import json
from collections import deque

import aio_pika
import pytest

from app.whatsapp.message_queue import MessageQueueService


class SimulatedBroker:
    """Fila + DLQ com a regra do RabbitMQ: `requeue=True` volta à fila como `redelivered`; `requeue=False` vai à DLQ."""

    def __init__(self, bodies):
        self.queue = deque((body, False) for body in bodies)
        self.dead_letters = []
        self.attempts = 0

    async def deliver_all(self, service, callback):
        while self.queue:
            body, redelivered = self.queue.popleft()
            self.attempts += 1
            await service._on_message(callback, self._incoming(body, redelivered))

    def _incoming(self, body, redelivered):
        broker = self

        class Incoming:
            routing_key = "webhooks.evolution"
            message_id = "msg-1"

            def __init__(self):
                self.body, self.redelivered = body, redelivered

            async def ack(self):
                pass

            async def nack(self, requeue=True):
                if requeue:
                    broker.queue.append((body, True))
                else:
                    broker.dead_letters.append(body)

            async def reject(self, requeue=False):
                await self.nack(requeue)

        return Incoming()


@pytest.mark.asyncio
async def test_a_message_that_keeps_failing_is_tried_twice_and_then_lands_in_the_dead_letter_queue():
    calls = []

    async def callback(payload):
        calls.append(payload["n"])
        raise RuntimeError("banco fora do ar")

    broker = SimulatedBroker([json.dumps({"n": 1}).encode()])

    await broker.deliver_all(MessageQueueService(), callback)

    assert calls == [1, 1]  # a primeira falha devolve à fila; a segunda (redelivered) manda para a DLQ
    assert broker.dead_letters == [json.dumps({"n": 1}).encode()]
    assert not broker.queue


@pytest.mark.asyncio
async def test_a_transient_failure_that_recovers_never_reaches_the_dead_letter_queue():
    calls = []

    async def callback(payload):
        calls.append(payload["n"])
        if len(calls) == 1:
            raise RuntimeError("falha momentânea")

    broker = SimulatedBroker([json.dumps({"n": 1}).encode()])

    await broker.deliver_all(MessageQueueService(), callback)

    assert calls == [1, 1]
    assert broker.dead_letters == []


@pytest.mark.asyncio
async def test_invalid_json_goes_straight_to_the_dead_letter_queue_without_a_retry():
    async def callback(_payload):
        raise AssertionError("não deveria ser chamado")

    broker = SimulatedBroker([b"{not json"])

    await broker.deliver_all(MessageQueueService(), callback)

    assert broker.attempts == 1
    assert broker.dead_letters == [b"{not json"]


@pytest.mark.asyncio
async def test_one_poison_message_does_not_hold_back_the_ones_behind_it():
    done = []

    async def callback(payload):
        if payload["n"] == 1:
            raise RuntimeError("venenosa")
        done.append(payload["n"])

    broker = SimulatedBroker([json.dumps({"n": n}).encode() for n in (1, 2, 3)])

    await broker.deliver_all(MessageQueueService(), callback)

    assert done == [2, 3]
    assert broker.dead_letters == [json.dumps({"n": 1}).encode()]


class _CapturingExchange:
    def __init__(self):
        self.published = []

    async def publish(self, message, routing_key):
        self.published.append((message, routing_key))


@pytest.mark.asyncio
async def test_binary_content_in_an_event_is_published_as_base64_json():
    exchange = _CapturingExchange()
    service = MessageQueueService()

    async def already_open():
        return None

    service._open = already_open
    service._channel = type("Channel", (), {"default_exchange": exchange})()

    assert await service.publish_webhook_event({"event": "messages.upsert", "data": {"media": [b"\x00\x01"]}})

    message, routing_key = exchange.published[0]
    assert routing_key == "webhooks.evolution"
    assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT
    body = json.loads(message.body)
    assert body["event"] == "messages.upsert"
    assert body["data"]["data"]["media"] == [base64.b64encode(b"\x00\x01").decode()]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event, expected",
    [
        ({"event": "messages.upsert", "data": {"key": {"id": "3EB0AAAA", "fromMe": False}}}, "3EB0AAAA"),
        ({"event": "connection.update", "data": {"state": "open"}}, None),
        ({"event": "messages.upsert", "data": {"key": {"fromMe": False}}}, None),
        ({"event": "x", "data": ["not", "a", "dict"]}, None),
    ],
)
async def test_the_amqp_message_id_is_the_whatsapp_key_id_when_the_event_has_one(event, expected):
    exchange = _CapturingExchange()
    service = MessageQueueService()

    async def already_open():
        return None

    service._open = already_open
    service._channel = type("Channel", (), {"default_exchange": exchange})()

    assert await service.publish_webhook_event(event)

    assert exchange.published[0][0].message_id == expected
