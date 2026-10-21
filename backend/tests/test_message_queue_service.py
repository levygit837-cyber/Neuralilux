"""Entrega de mensagens do RabbitMQ ao callback: ack, rejeição, requeue e concorrência."""
import asyncio
import json

import pytest

from app.services.message_queue_service import MessageQueueService


class FakeIncoming:
    """Mensagem entregue pelo aio-pika; registra como foi resolvida."""

    def __init__(self, body: bytes, routing_key: str = "webhooks.evolution", redelivered: bool = False):
        self.body = body
        self.routing_key = routing_key
        self.redelivered = redelivered
        self.message_id = "msg-1"
        self.resolution = None

    async def ack(self):
        self.resolution = "ack"

    async def nack(self, requeue=True):
        self.resolution = f"nack(requeue={requeue})"

    async def reject(self, requeue=False):
        self.resolution = f"reject(requeue={requeue})"


def _body(payload) -> bytes:
    return json.dumps(payload).encode()


@pytest.mark.asyncio
async def test_successful_callback_acks_the_message_with_the_decoded_payload():
    received = []

    async def callback(payload):
        received.append(payload)

    message = FakeIncoming(_body({"event": "messages.upsert"}))

    await MessageQueueService()._on_message(callback, message)

    assert received == [{"event": "messages.upsert"}]
    assert message.resolution == "ack"


@pytest.mark.asyncio
async def test_invalid_json_is_rejected_without_requeue_and_never_reaches_the_callback():
    async def callback(_payload):
        raise AssertionError("não deveria ser chamado")

    message = FakeIncoming(b"{not json")

    await MessageQueueService()._on_message(callback, message)

    assert message.resolution == "reject(requeue=False)"


@pytest.mark.asyncio
async def test_first_failure_requeues_the_message():
    async def callback(_payload):
        raise RuntimeError("banco fora do ar")

    message = FakeIncoming(_body({"event": "x"}))

    await MessageQueueService()._on_message(callback, message)

    assert message.resolution == "nack(requeue=True)"


@pytest.mark.asyncio
async def test_failure_on_redelivery_drops_the_message_instead_of_looping():
    async def callback(_payload):
        raise RuntimeError("mensagem venenosa")

    message = FakeIncoming(_body({"event": "x"}), redelivered=True)

    await MessageQueueService()._on_message(callback, message)

    assert message.resolution == "nack(requeue=False)"


@pytest.mark.asyncio
async def test_redelivered_message_that_succeeds_is_acked():
    async def callback(_payload):
        return None

    message = FakeIncoming(_body({"event": "x"}), redelivered=True)

    await MessageQueueService()._on_message(callback, message)

    assert message.resolution == "ack"


@pytest.mark.asyncio
async def test_deliveries_run_concurrently_in_one_event_loop():
    """Duas mensagens em voo ao mesmo tempo: uma só é concluída quando a outra também começou."""
    service = MessageQueueService()
    both_started = asyncio.Event()
    started = []

    async def callback(payload):
        started.append(payload["n"])
        if len(started) == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=1)

    first, second = FakeIncoming(_body({"n": 1})), FakeIncoming(_body({"n": 2}))

    await asyncio.gather(service._on_message(callback, first), service._on_message(callback, second))

    assert (first.resolution, second.resolution) == ("ack", "ack")


@pytest.mark.asyncio
async def test_stop_waits_for_in_flight_deliveries_before_returning():
    service = MessageQueueService()
    release = asyncio.Event()
    finished = []

    async def callback(_payload):
        await release.wait()
        finished.append(True)

    delivery = asyncio.create_task(service._on_message(callback, FakeIncoming(_body({}))))
    await asyncio.sleep(0)  # a entrega entra em voo

    stopping = asyncio.create_task(service.stop_consuming())
    await asyncio.sleep(0.01)
    assert not stopping.done()  # ainda esperando a entrega

    release.set()
    await stopping
    await delivery

    assert finished == [True]
