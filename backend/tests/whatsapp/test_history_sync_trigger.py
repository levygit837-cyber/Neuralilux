"""Eventos da Evolution que disparam a importação de histórico: no máximo uma por Instance."""
import asyncio
from unittest.mock import MagicMock

import pytest

from app.whatsapp import consumer as consumer_module, history_sync, history_trigger, status_events
from app.whatsapp.consumer import WhatsAppMessageConsumer
from consumer_helpers import process


def _event(event, **data):
    return {"event": event, "data": {"instance": "evo-t7", "data": data}}


async def _until_started(syncs, count=1):
    """O início do sync passa por saltos de thread (busca da Instance, abertura da Session): espera a condição."""
    for _ in range(400):
        if len(syncs["started"]) >= count:
            return
        await asyncio.sleep(0.005)


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
    await _until_started(syncs)

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
    await _until_started(syncs)
    assert syncs["started"] == [world["instance"].id]
    syncs["release"].set()
    await consumer.drain()


@pytest.mark.asyncio
async def test_second_event_is_ignored_while_a_sync_runs_and_allowed_after(db, world, syncs):
    consumer = WhatsAppMessageConsumer()
    await consumer.process_webhook_event(_event("messages.set"))
    await consumer.process_webhook_event(_event("chats.set"))
    await _until_started(syncs)
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
async def test_worker_skips_with_an_info_log_when_another_process_is_importing(db, world, monkeypatch):
    async def busy(db, instance):
        raise history_sync.SyncAlreadyRunning(instance.id)

    logs = MagicMock()
    monkeypatch.setattr(history_sync, "sync_instance", busy)
    monkeypatch.setattr(history_trigger, "logger", logs)
    consumer = WhatsAppMessageConsumer()

    await process(consumer, _event("messages.set"))

    # Outro processo importando não é falha: sem `logger.exception`, e a Instance fica livre para a próxima.
    logs.exception.assert_not_called()
    assert "History sync skipped: another process is already importing" in [
        call.args[0] for call in logs.info.call_args_list
    ]
    assert consumer._syncing == set()


@pytest.mark.asyncio
async def test_replayed_stale_open_does_not_start_a_history_sync(world, syncs, monkeypatch):
    monkeypatch.setattr(status_events, "_last_connection_event", {})

    def connection(state, date_time):
        event = _event("connection.update", state=state)
        event["data"]["date_time"] = date_time
        return event

    consumer = WhatsAppMessageConsumer()
    await consumer.process_webhook_event(connection("open", "2026-01-01T12:10:00.000-03:00"))
    await _until_started(syncs)
    syncs["release"].set()
    await consumer.drain()
    assert len(syncs["started"]) == 1

    await consumer.process_webhook_event(connection("close", "2026-01-01T12:20:00.000-03:00"))
    await consumer.process_webhook_event(connection("open", "2026-01-01T12:10:00.000-03:00"))  # reenvio velho
    await consumer.drain()

    assert len(syncs["started"]) == 1


@pytest.fixture
def guarded(monkeypatch):
    """Intervalo de reimportação ligado (300 s) sobre um Redis em memória."""
    import fakeredis

    from app.core.config import settings
    from app.whatsapp import reimport_guard

    server = fakeredis.FakeServer()
    monkeypatch.setattr(settings, "HISTORY_REIMPORT_MIN_INTERVAL_SECONDS", 300)
    monkeypatch.setattr(reimport_guard, "_redis", None)
    monkeypatch.setattr(reimport_guard, "_redis_loop", None)
    monkeypatch.setattr(
        reimport_guard,
        "Redis",
        type("R", (), {"from_url": staticmethod(lambda *a, **k: fakeredis.FakeAsyncRedis(server=server, decode_responses=True))}),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("first,second", [
    (_event("chats.upsert"), _event("chats.upsert")),
    (_event("connection.update", state="open"), _event("connection.update", state="open")),
    (_event("chats.upsert"), _event("connection.update", state="open")),
])
async def test_a_repeated_reimport_inside_the_interval_is_ignored_with_a_log(db, world, syncs, guarded, first, second):
    import structlog

    consumer = WhatsAppMessageConsumer()
    await consumer.process_webhook_event(first)
    await _until_started(syncs)
    syncs["release"].set()
    await consumer.drain()
    assert len(syncs["started"]) == 1

    with structlog.testing.capture_logs() as logs:
        await consumer.process_webhook_event(second)
        await consumer.drain()

    assert len(syncs["started"]) == 1  # a segunda ocorrência não importou
    ignored = [log for log in logs if log["event"].startswith("History reimport ignored")]
    assert len(ignored) == 1 and ignored[0]["instance_id"] == world["instance"].id


@pytest.mark.asyncio
async def test_the_initial_load_events_are_not_held_back_by_the_interval(db, world, syncs, guarded):
    consumer = WhatsAppMessageConsumer()
    syncs["release"].set()
    for event in ("messages.set", "chats.set", "contacts.set"):
        await consumer.process_webhook_event(_event(event))
        await consumer.drain()

    assert len(syncs["started"]) == 3
