"""Eventos da Evolution que disparam a importação de histórico: no máximo uma por Instance."""
import asyncio

import pytest

from app.whatsapp import history_sync
from app.whatsapp.consumer import WhatsAppMessageConsumer
from consumer_helpers import process


def _event(event, **data):
    return {"event": event, "data": {"instance": "evo-t7", "data": data}}


@pytest.fixture
def syncs(monkeypatch):
    calls = {"started": [], "release": asyncio.Event()}

    async def fake_sync(db, instance):
        calls["started"].append(instance.id)
        await calls["release"].wait()
        return {"conversations": 0, "messages": 0}

    monkeypatch.setattr(history_sync, "sync_instance", fake_sync)
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize("event", ["messages.set", "chats.set", "contacts.set", "chats.upsert"])
async def test_history_events_schedule_one_sync(db, world, syncs, event):
    consumer = WhatsAppMessageConsumer()
    await consumer.process_webhook_event(_event(event))
    await asyncio.sleep(0)

    assert syncs["started"] == [world["instance"].id]
    syncs["release"].set()
    await consumer.drain()


@pytest.mark.asyncio
async def test_connection_open_schedules_sync_but_close_does_not(db, world, syncs):
    consumer = WhatsAppMessageConsumer()
    await consumer.process_webhook_event(_event("connection.update", state="close"))
    await asyncio.sleep(0)
    assert syncs["started"] == []

    await consumer.process_webhook_event(_event("connection.update", state="open"))
    await asyncio.sleep(0)
    assert syncs["started"] == [world["instance"].id]
    syncs["release"].set()
    await consumer.drain()


@pytest.mark.asyncio
async def test_second_event_is_ignored_while_a_sync_runs_and_allowed_after(db, world, syncs):
    consumer = WhatsAppMessageConsumer()
    await consumer.process_webhook_event(_event("messages.set"))
    await consumer.process_webhook_event(_event("chats.set"))
    await asyncio.sleep(0)
    assert len(syncs["started"]) == 1

    syncs["release"].set()
    await consumer.drain()
    await consumer.process_webhook_event(_event("messages.set"))
    await consumer.drain()
    assert len(syncs["started"]) == 2


@pytest.mark.asyncio
async def test_sync_for_unknown_instance_is_ignored(db, world, syncs):
    consumer = WhatsAppMessageConsumer()
    payload = _event("messages.set")
    payload["data"]["instance"] = "outra"

    await process(consumer, payload)

    assert syncs["started"] == []


@pytest.mark.asyncio
async def test_failed_sync_is_logged_and_frees_the_instance(db, world, monkeypatch):
    attempts = []

    async def failing_sync(db, instance):
        attempts.append(1)
        raise RuntimeError("Evolution fora do ar")

    monkeypatch.setattr(history_sync, "sync_instance", failing_sync)
    consumer = WhatsAppMessageConsumer()

    await process(consumer, _event("messages.set"))
    await process(consumer, _event("messages.set"))

    assert len(attempts) == 2


@pytest.mark.asyncio
async def test_worker_skips_silently_when_another_process_is_importing(db, world, monkeypatch):
    async def busy(db, instance):
        raise history_sync.SyncAlreadyRunning(instance.id)

    monkeypatch.setattr(history_sync, "sync_instance", busy)
    consumer = WhatsAppMessageConsumer()

    await process(consumer, _event("messages.set"))

    assert consumer._syncing == set()
