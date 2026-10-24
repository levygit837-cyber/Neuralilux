"""Consumer: Messages picadas viram um Turn, "digitando" durante o Turn e nenhuma Message perdida ou duplicada."""
import asyncio
from datetime import datetime, timezone

import pytest

from app.agent import executor
from app.agent.loop import TurnResult
from app.core.config import settings
from app.whatsapp.consumer import WhatsAppMessageConsumer
from app.whatsapp.evolution_client import EvolutionAPIError, evolution_api
from app.whatsapp.turn_batcher import TurnBatcher
from consumer_helpers import messages, upsert
from tests.clock_helpers import FakeClock, settle

pytestmark = pytest.mark.asyncio

OTHER_JID = "5511900000002@s.whatsapp.net"


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(settings, "DEBOUNCE_SECONDS", 3.0)
    return FakeClock()


@pytest.fixture
def consumer(clock):
    instance = WhatsAppMessageConsumer()
    instance._batcher = TurnBatcher(monotonic=clock.monotonic, sleep=clock.sleep)
    return instance


def deliver(consumer, **kwargs):
    return asyncio.create_task(consumer.process_webhook_event(upsert(**kwargs)))


async def test_three_quick_messages_get_one_turn_and_one_reply(db, world, consumer, clock):
    tasks = [deliver(consumer, text="oi", message_id="in-1")]
    await settle()
    await clock.advance(1)
    tasks.append(deliver(consumer, text="quero", message_id="in-2"))
    await settle()
    await clock.advance(1)
    tasks.append(deliver(consumer, text="uma calabresa", message_id="in-3"))
    await settle()
    assert world["turns"] == [] and world["sent"] == []

    await clock.advance(3)
    await asyncio.gather(*tasks)
    await consumer.drain()

    assert world["turns"] == ["oi\nquero\numa calabresa"]
    assert len(world["sent"]) == 1
    incoming = [m.content for m in messages(db) if not m.is_from_me]
    assert incoming == ["oi", "quero", "uma calabresa"]  # cada Message continua gravada por inteiro


async def test_followers_are_stored_while_the_leader_waits(db, world, consumer, clock):
    leader = deliver(consumer, text="oi", message_id="in-1")
    await settle()
    follower = deliver(consumer, text="quero", message_id="in-2")
    await settle()

    assert follower.done() and not leader.done()
    assert [m.content for m in messages(db)] == ["oi", "quero"]

    await clock.advance(3)
    await leader


async def test_message_arriving_during_a_turn_is_answered_in_the_next_turn_without_overlap(
    db, world, consumer, clock, monkeypatch
):
    gate = asyncio.Event()
    running, peak = 0, 0

    async def slow_turn(db, conversation, contact, instance, text, received_at=None, message_ids=(), deferred_ids=(), agent=None, packs=()):
        nonlocal running, peak
        world["turns"].append(text)
        running += 1
        peak = max(peak, running)
        try:
            if len(world["turns"]) == 1:
                await gate.wait()
        finally:
            running -= 1
        return TurnResult(reply_text=f"re:{text}")

    monkeypatch.setattr(executor, "handle_incoming", slow_turn)
    first = deliver(consumer, text="oi", message_id="in-1")
    await settle()
    await clock.advance(3)  # o primeiro Turn começa e fica preso
    assert world["turns"] == ["oi"]

    late = deliver(consumer, text="sem cebola", message_id="in-2")
    await settle()
    assert late.done() and world["turns"] == ["oi"]

    gate.set()
    await settle()
    await clock.advance(3)
    await first
    await consumer.drain()

    assert world["turns"] == ["oi", "sem cebola"]
    assert [sent["text"] for sent in world["sent"]] == ["re:oi", "re:sem cebola"]
    assert peak == 1


async def test_different_conversations_group_independently_and_run_in_parallel(db, world, consumer, clock):
    a1 = deliver(consumer, text="a1", message_id="a-1")
    b1 = deliver(consumer, text="b1", remote_jid=OTHER_JID, message_id="b-1")
    await settle()
    a2 = deliver(consumer, text="a2", message_id="a-2")
    await settle()

    await clock.advance(3)
    await asyncio.gather(a1, b1, a2)

    assert sorted(world["turns"]) == ["a1\na2", "b1"]
    assert {sent["remote_jid"] for sent in world["sent"]} == {upsert()["data"]["data"]["key"]["remoteJid"], OTHER_JID}


# --- "digitando" -----------------------------------------------------------------------------------


async def test_typing_is_shown_while_the_turn_runs_and_stops_after_the_reply(db, world, consumer, clock, presence, monkeypatch):
    seen_during_turn = []

    async def turn(db, conversation, contact, instance, text, received_at=None, message_ids=(), deferred_ids=(), agent=None, packs=()):
        await settle()
        seen_during_turn.append(len(presence))
        return TurnResult(reply_text="Resposta")

    monkeypatch.setattr(executor, "handle_incoming", turn)
    task = deliver(consumer, text="oi")
    await settle()
    await clock.advance(3)
    await task

    assert seen_during_turn == [1]
    assert presence[0] == {"instance_name": "evo-t7", "remote_jid": upsert()["data"]["data"]["key"]["remoteJid"], "presence": "composing"}
    assert len(world["sent"]) == 1


async def test_typing_failure_does_not_block_the_reply(db, world, consumer, clock, monkeypatch):
    async def broken_presence(instance_name, remote_jid, presence="composing", delay_ms=0):
        raise EvolutionAPIError("instância desconectada", status_code=500)

    monkeypatch.setattr(evolution_api, "send_presence", broken_presence)
    task = deliver(consumer, text="oi")
    await settle()
    await clock.advance(3)
    await task
    await consumer.drain()

    assert world["turns"] == ["oi"]
    assert len(world["sent"]) == 1


async def test_typing_is_not_shown_when_the_agent_will_not_answer(db, world, consumer, clock, presence):
    world["instance"].agent_enabled = False
    db.commit()

    task = deliver(consumer, text="oi")
    await settle()
    await clock.advance(3)
    await task

    assert presence == [] and world["turns"] == []


async def test_grouped_turn_is_triggered_at_the_oldest_message_of_the_group(db, world, consumer, clock, monkeypatch):
    """O Recap só vale se a Message que dispara o Turn é posterior à entrega dele: a mais antiga do grupo manda."""
    received = []

    async def turn(db, conversation, contact, instance, text, received_at=None, message_ids=(), deferred_ids=(), agent=None, packs=()):
        received.append(received_at)
        return TurnResult(reply_text=None)

    monkeypatch.setattr(executor, "handle_incoming", turn)
    base = int(datetime.now(timezone.utc).timestamp()) - 60
    tasks = [deliver(consumer, text="oi", message_id="in-1", ts=base + 5)]
    await settle()
    tasks.append(deliver(consumer, text="sim", message_id="in-2", ts=base))
    await settle()
    await clock.advance(3)
    await asyncio.gather(*tasks)

    assert received == [datetime.fromtimestamp(base, tz=timezone.utc)]
