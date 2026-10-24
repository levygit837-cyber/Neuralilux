"""Consumer do webhook da Evolution: concorrência, Summary, shutdown, realtime e mensagens malformadas."""
import asyncio

import pytest

from app.agent import executor
from app.agent.loop import TurnResult
from app.models import Conversation
from app.realtime.event_bus import realtime_event_bus
from app.whatsapp import consumer as consumer_module
from app.whatsapp.consumer import WhatsAppMessageConsumer, parse_content
from consumer_helpers import messages, process, upsert


@pytest.mark.asyncio
async def test_messages_of_one_conversation_run_in_order_and_never_overlap(db, world, monkeypatch):
    running, overlaps, order = 0, [], []

    async def slow_turn(db, conversation, contact, instance, text, received_at=None, message_ids=(), deferred_ids=(), agent=None):
        nonlocal running
        running += 1
        overlaps.append(running)
        order.append(text)
        await asyncio.sleep(0.02)
        running -= 1
        return TurnResult(reply_text=None)

    monkeypatch.setattr(executor, "handle_incoming", slow_turn)
    consumer = WhatsAppMessageConsumer()

    await asyncio.gather(
        *(consumer.process_webhook_event(upsert(text=f"m{n}", message_id=f"in-{n}")) for n in range(4))
    )
    await consumer.drain()

    assert max(overlaps) == 1
    assert order == ["m0", "m1", "m2", "m3"]


@pytest.mark.asyncio
async def test_different_conversations_are_processed_in_parallel(db, world, monkeypatch):
    both_inside = asyncio.Event()
    inside = []

    async def rendezvous_turn(db, conversation, contact, instance, text, received_at=None, message_ids=(), deferred_ids=(), agent=None):
        inside.append(text)
        if len(inside) == 2:
            both_inside.set()
        await asyncio.wait_for(both_inside.wait(), timeout=2)  # só passa se a outra Conversation entrou junto
        return TurnResult(reply_text=None)

    monkeypatch.setattr(executor, "handle_incoming", rendezvous_turn)
    consumer = WhatsAppMessageConsumer()

    await asyncio.gather(
        consumer.process_webhook_event(upsert(text="a", remote_jid="5511900000001@s.whatsapp.net", message_id="a-1")),
        consumer.process_webhook_event(upsert(text="b", remote_jid="5511900000002@s.whatsapp.net", message_id="b-1")),
    )

    assert sorted(inside) == ["a", "b"]


@pytest.mark.asyncio
async def test_conversation_locks_are_released_when_idle(db, world):
    consumer = WhatsAppMessageConsumer()

    await process(consumer, upsert())

    assert consumer._locks == {}


# --- Summary fora do caminho crítico ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_does_not_delay_the_reply_and_finishes_on_the_persistent_loop(db, world, monkeypatch):
    release = asyncio.Event()
    finished = []

    async def slow_refresh(conversation_id):
        await release.wait()
        finished.append(conversation_id)

    monkeypatch.setattr(executor, "refresh_summary", slow_refresh)
    consumer = WhatsAppMessageConsumer()

    # O callback termina e a resposta já saiu enquanto o Summary segue pendente.
    await asyncio.wait_for(consumer.process_webhook_event(upsert()), timeout=1)
    assert len(world["sent"]) == 1 and finished == []

    release.set()
    await consumer.drain()
    assert finished == [db.query(Conversation).one().id]


@pytest.mark.asyncio
async def test_failing_summary_never_surfaces(db, world, monkeypatch):
    async def broken_refresh(_conversation_id):
        raise RuntimeError("gateway fora")

    monkeypatch.setattr(executor, "refresh_summary", broken_refresh)
    consumer = WhatsAppMessageConsumer()

    await process(consumer, upsert())

    assert len(world["sent"]) == 1


@pytest.fixture
def stoppable(monkeypatch):
    """`stop()` sem broker: o consumer só precisa que `stop_consuming` termine."""
    async def stop_consuming():
        return None

    monkeypatch.setattr(consumer_module.message_queue_service, "stop_consuming", stop_consuming)


@pytest.mark.asyncio
async def test_stop_waits_for_a_pending_summary(db, world, stoppable, monkeypatch):
    finished = []

    async def slow_refresh(conversation_id):
        await asyncio.sleep(0.05)
        finished.append(conversation_id)

    monkeypatch.setattr(executor, "refresh_summary", slow_refresh)
    consumer = WhatsAppMessageConsumer()
    await consumer.process_webhook_event(upsert())
    assert finished == []

    await consumer.stop()

    assert finished == [db.query(Conversation).one().id]
    assert consumer._background == set()


@pytest.mark.asyncio
async def test_stop_cancels_a_summary_that_outlives_the_drain_timeout(db, world, stoppable, monkeypatch):
    monkeypatch.setattr(consumer_module, "DRAIN_TIMEOUT", 0.05)
    cancelled = []

    async def stuck_refresh(_conversation_id):
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    monkeypatch.setattr(executor, "refresh_summary", stuck_refresh)
    consumer = WhatsAppMessageConsumer()
    await consumer.process_webhook_event(upsert())

    await asyncio.wait_for(consumer.stop(), timeout=2)

    assert cancelled == [True]


# --- Realtime fora do caminho crítico; mensagens malformadas -----------------------------------------


@pytest.mark.asyncio
async def test_realtime_failure_does_not_stop_the_agent_or_the_reply(db, world, monkeypatch):
    async def broken_publish(_event):
        raise ConnectionError("redis fora do ar")

    monkeypatch.setattr(realtime_event_bus, "publish", broken_publish)

    await process(WhatsAppMessageConsumer(), upsert())

    assert world["turns"] == ["Oi"]
    assert len(world["sent"]) == 1
    assert sorted(m.message_id for m in messages(db)) == ["in-1", "out-1"]  # a reply ficou gravada mesmo assim


@pytest.mark.parametrize(
    "message",
    [
        {"extendedTextMessage": None},
        {"imageMessage": None},
        {"ephemeralMessage": {"message": None}},
        {"conversation": None},
        None,
    ],
)
def test_parse_content_survives_null_message_keys(message):
    assert parse_content(message).text == ""


@pytest.mark.asyncio
async def test_message_with_null_extended_text_is_stored_and_not_answered(db, world):
    await process(WhatsAppMessageConsumer(), upsert(message={"extendedTextMessage": None}))

    assert [m.message_id for m in messages(db)] == ["in-1"]
    assert world["turns"] == [] and world["sent"] == []
