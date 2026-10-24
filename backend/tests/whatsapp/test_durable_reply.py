"""#91: nenhuma Message do Contact fica sem resposta, e nenhuma é respondida duas vezes."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.agent import executor
from app.agent.loop import TurnResult
from app.core.config import settings
from app.models import Conversation, Instance, Message
from app.whatsapp import consumer as consumer_module, turn_state
from app.whatsapp.consumer import WhatsAppMessageConsumer
from app.whatsapp.turn_runner import TurnRunner
from consumer_helpers import JID, messages, process, upsert

pytestmark = pytest.mark.asyncio


def incoming(db):
    return [m for m in messages(db) if not m.is_from_me]


def states(db):
    return [(m.content, m.turn_state, m.turn_reason) for m in incoming(db)]


async def leave_pending(db, **kwargs):
    """Message do Contact gravada como pending cujo Turn nunca começa (o worker caiu logo após o ack)."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(TurnRunner, "spawn", lambda self, *args, **kw: None)
        await WhatsAppMessageConsumer().process_webhook_event(upsert(**kwargs))


def lose_ownership(db, reason=turn_state.RUNNING, age_seconds=3600):
    """O dono da posse sumiu: a posse venceu."""
    past = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    db.query(Message).filter(Message.turn_state == turn_state.PENDING).update(
        {"turn_claimed_at": past, "turn_reason": reason}
    )
    db.commit()


@pytest.fixture
def stoppable(monkeypatch):
    async def stop_consuming():
        return None

    monkeypatch.setattr(consumer_module.message_queue_service, "stop_consuming", stop_consuming)


# --- o estado nasce com a Message ----------------------------------------------------------------------


async def test_message_is_acked_as_pending_before_the_turn_runs(db, world):
    await leave_pending(db, text="Oi")

    assert states(db) == [("Oi", turn_state.PENDING, turn_state.QUEUED)]
    assert world["turns"] == []


async def test_answered_message_records_the_outcome(db, world):
    await process(WhatsAppMessageConsumer(), upsert(text="Oi"))

    assert states(db) == [("Oi", turn_state.ANSWERED, turn_state.REPLIED)]


async def test_messages_that_never_get_a_turn_are_not_pending(db, world):
    consumer = WhatsAppMessageConsumer()
    await process(consumer, upsert(text="grupo", remote_jid="120363@g.us", message_id="g-1"))
    await process(consumer, upsert(text="meu", from_me=True, message_id="me-1"))
    await process(consumer, upsert(text="lid", remote_jid="99@lid", message_id="l-1"))

    assert db.query(Message).filter(Message.turn_state == turn_state.PENDING).count() == 0
    assert {m.message_id: m.turn_reason for m in messages(db) if m.turn_state} == {"l-1": turn_state.SKIP_UNRESOLVED_LID}
    assert world["turns"] == []


# --- worker caiu no meio do Turn -----------------------------------------------------------------------


async def test_worker_killed_mid_turn_is_recovered_with_a_single_reply(db, world, monkeypatch):
    gate = asyncio.Event()

    async def hanging_turn(db, conversation, contact, instance, text, received_at=None, **kwargs):
        world["turns"].append(text)
        await gate.wait()
        return TurnResult(reply_text="nunca")

    monkeypatch.setattr(executor, "handle_incoming", hanging_turn)
    first = WhatsAppMessageConsumer()
    await first.process_webhook_event(upsert(text="Oi"))
    await asyncio.sleep(0.05)
    assert states(db) == [("Oi", turn_state.PENDING, turn_state.RUNNING)]

    # kill -9: as tasks somem sem escrever nada no banco
    with monkeypatch.context() as patch:
        patch.setattr(turn_state, "release", lambda *args, **kwargs: None)
        patch.setattr(turn_state, "unclaim", lambda *args, **kwargs: None)
        for task in list(first.runner.tasks):
            task.cancel()
        await asyncio.gather(*first.runner.tasks, return_exceptions=True)
    assert world["sent"] == []

    async def fresh_turn(db, conversation, contact, instance, text, received_at=None, **kwargs):
        world["turns"].append(text)
        return TurnResult(reply_text="Resposta")

    monkeypatch.setattr(executor, "handle_incoming", fresh_turn)
    lose_ownership(db)
    second = WhatsAppMessageConsumer()
    assert await second.recovery.sweep() == 1
    await second.drain()

    assert len(world["sent"]) == 1
    assert states(db) == [("Oi", turn_state.ANSWERED, turn_state.REPLIED)]
    assert await second.recovery.sweep() == 0


async def test_pending_message_with_a_live_owner_is_left_alone(db, world):
    await leave_pending(db, text="Oi")  # a posse é de agora e o dono pode estar só esperando o debounce

    other = WhatsAppMessageConsumer()
    assert await other.recovery.sweep() == 0
    assert world["turns"] == []


async def test_failed_turn_is_retried_after_the_lease(db, world, monkeypatch):
    calls = []

    async def flaky_turn(db, conversation, contact, instance, text, received_at=None, **kwargs):
        calls.append(text)
        if len(calls) == 1:
            raise RuntimeError("gateway fora")
        return TurnResult(reply_text="Resposta")

    monkeypatch.setattr(executor, "handle_incoming", flaky_turn)
    consumer = WhatsAppMessageConsumer()
    await process(consumer, upsert(text="Oi"))
    assert states(db)[0][1:] == (turn_state.PENDING, turn_state.FAILED) or states(db)[0][1] == turn_state.ANSWERED

    lose_ownership(db, reason=turn_state.FAILED)
    await consumer.recovery.sweep()
    await consumer.drain()

    assert len(world["sent"]) >= 1
    assert states(db)[0][1] == turn_state.ANSWERED


# --- resposta que já saiu não sai de novo --------------------------------------------------------------


async def test_reply_already_sent_is_not_resent_after_a_crash(db, world):
    consumer = WhatsAppMessageConsumer()
    await process(consumer, upsert(text="Oi"))
    assert len(world["sent"]) == 1
    # a resposta saiu e foi gravada, mas o worker caiu antes de fechar a Message
    db.query(Message).filter(Message.is_from_me.is_(False)).update(
        {"turn_state": turn_state.PENDING, "turn_reason": turn_state.RUNNING,
         "turn_claimed_at": datetime.now(timezone.utc) - timedelta(seconds=3600)}
    )
    db.query(Message).filter(Message.is_from_me.is_(True)).update({"timestamp": datetime.now(timezone.utc)})
    db.commit()

    other = WhatsAppMessageConsumer()
    assert await other.recovery.sweep() == 0

    assert len(world["sent"]) == 1 and world["turns"] == ["Oi"]
    assert states(db) == [("Oi", turn_state.ANSWERED, turn_state.SENT_ELSEWHERE)]


async def test_webhook_echo_of_the_reply_closes_the_pending_message_without_resending(db, world):
    await leave_pending(db, text="Oi")
    lose_ownership(db)  # o Turn começou e o dono caiu depois de enviar

    other = WhatsAppMessageConsumer()
    await process(other, upsert(text="Resposta", from_me=True, message_id="echo-1"))
    assert states(db) == [("Oi", turn_state.ANSWERED, turn_state.SENT_ELSEWHERE)]

    assert await other.recovery.sweep() == 0
    assert world["turns"] == [] and world["sent"] == []


async def test_attendant_message_after_a_queued_one_does_not_close_it(db, world):
    await leave_pending(db, text="Oi")  # ainda `queued`: nenhum Turn começou, a resposta do Attendant é de outro assunto

    await process(WhatsAppMessageConsumer(), upsert(text="Olá!", from_me=True, message_id="att-1"))

    assert states(db) == [("Oi", turn_state.PENDING, turn_state.QUEUED)]


# --- redelivery ----------------------------------------------------------------------------------------


async def test_redelivery_of_a_pending_message_resumes_its_turn_without_saving_again(db, world):
    await leave_pending(db, text="Oi")
    lose_ownership(db, reason=turn_state.RELEASED, age_seconds=0)

    await process(WhatsAppMessageConsumer(), upsert(text="Oi"))

    assert len(incoming(db)) == 1
    assert world["turns"] == ["Oi"] and len(world["sent"]) == 1
    assert states(db) == [("Oi", turn_state.ANSWERED, turn_state.REPLIED)]


async def test_redelivery_while_the_turn_is_running_does_not_start_another(db, world, monkeypatch):
    gate = asyncio.Event()

    async def slow_turn(db, conversation, contact, instance, text, received_at=None, **kwargs):
        world["turns"].append(text)
        await gate.wait()
        return TurnResult(reply_text="Resposta")

    monkeypatch.setattr(executor, "handle_incoming", slow_turn)
    consumer = WhatsAppMessageConsumer()
    await consumer.process_webhook_event(upsert(text="Oi"))
    await asyncio.sleep(0.05)
    await consumer.process_webhook_event(upsert(text="Oi"))
    gate.set()
    await consumer.drain()

    assert world["turns"] == ["Oi"] and len(world["sent"]) == 1


# --- regras de skip na recuperação ---------------------------------------------------------------------


async def test_recovery_marks_old_messages_as_stale_and_answers_the_recent_ones_in_one_turn(db, world):
    base = int(datetime.now(timezone.utc).timestamp())
    await leave_pending(db, text="velha", message_id="in-old")
    await leave_pending(db, text="nova 1", message_id="in-1", ts=base - 2)
    await leave_pending(db, text="nova 2", message_id="in-2", ts=base - 1)
    old = datetime.now(timezone.utc) - timedelta(seconds=settings.TURN_RECOVERY_MAX_AGE_SECONDS + 60)
    db.query(Message).filter(Message.message_id == "in-old").update({"timestamp": old})
    db.commit()
    lose_ownership(db, reason=turn_state.QUEUED)

    consumer = WhatsAppMessageConsumer()
    assert await consumer.recovery.sweep() == 2
    await consumer.drain()

    assert world["turns"] == ["nova 1\nnova 2"] and len(world["sent"]) == 1
    assert {c: (s, r) for c, s, r in states(db)} == {
        "velha": (turn_state.SKIPPED, turn_state.SKIP_STALE),
        "nova 1": (turn_state.ANSWERED, turn_state.REPLIED),
        "nova 2": (turn_state.ANSWERED, turn_state.REPLIED),
    }


async def test_recovery_respects_handoff(db, world):
    await leave_pending(db, text="Oi")
    db.query(Conversation).update({"human_in_loop": True})
    db.commit()
    lose_ownership(db, reason=turn_state.QUEUED)

    consumer = WhatsAppMessageConsumer()
    assert await consumer.recovery.sweep() == 0

    assert states(db) == [("Oi", turn_state.SKIPPED, turn_state.SKIP_HANDOFF)]
    assert world["turns"] == [] and world["sent"] == []


async def test_recovery_respects_agent_disabled(db, world):
    await leave_pending(db, text="Oi")
    db.query(Instance).update({"agent_enabled": False})
    db.commit()
    lose_ownership(db, reason=turn_state.QUEUED)

    consumer = WhatsAppMessageConsumer()
    await consumer.recovery.sweep()
    await consumer.drain()

    assert states(db) == [("Oi", turn_state.SKIPPED, turn_state.SKIP_AGENT_DISABLED)]
    assert world["turns"] == [] and world["sent"] == []


async def test_recovery_answers_media_with_the_fixed_reply(db, world):
    await leave_pending(db, message={"imageMessage": {"caption": ""}}, message_id="img-1")
    lose_ownership(db, reason=turn_state.QUEUED)

    consumer = WhatsAppMessageConsumer()
    await consumer.recovery.sweep()
    await consumer.drain()

    assert world["turns"] == [] and len(world["sent"]) == 1
    assert states(db)[0][1:] == (turn_state.ANSWERED, turn_state.MEDIA_REPLY)


# --- vários workers ------------------------------------------------------------------------------------


async def test_two_recoveries_at_the_same_time_answer_once(db, world):
    await leave_pending(db, text="Oi")
    lose_ownership(db, reason=turn_state.QUEUED)

    first, second = WhatsAppMessageConsumer(), WhatsAppMessageConsumer()
    swept = await asyncio.gather(first.recovery.sweep(), second.recovery.sweep())
    await asyncio.gather(first.drain(), second.drain())

    assert sorted(swept) == [0, 1]
    assert world["turns"] == ["Oi"] and len(world["sent"]) == 1


# --- o loop não espera o Gateway -----------------------------------------------------------------------


async def test_twenty_conversations_with_a_slow_gateway_do_not_delay_a_connection_update(db, world, monkeypatch):
    gate = asyncio.Event()
    running = peak = 0

    async def slow_turn(db, conversation, contact, instance, text, received_at=None, **kwargs):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        try:
            await gate.wait()
        finally:
            running -= 1
        return TurnResult(reply_text="Resposta")

    monkeypatch.setattr(executor, "handle_incoming", slow_turn)
    monkeypatch.setattr(settings, "TURN_CONCURRENCY", 3)
    consumer = WhatsAppMessageConsumer()

    for n in range(20):
        await asyncio.wait_for(
            consumer.process_webhook_event(
                upsert(text=f"oi {n}", remote_jid=f"551190000{n:04d}@s.whatsapp.net", message_id=f"in-{n}")
            ),
            timeout=1,
        )
    await asyncio.wait_for(
        consumer.process_webhook_event(
            {"event": "connection.update", "data": {"instance": "evo-t7", "data": {"state": "close"}}}
        ),
        timeout=1,
    )
    await asyncio.sleep(0.05)
    assert len(incoming(db)) == 20 and peak == 3  # entregues e confirmadas; só `TURN_CONCURRENCY` falam com o Gateway

    gate.set()
    await asyncio.wait_for(consumer.drain(), timeout=10)
    assert len(world["sent"]) == 20
    assert {s for _, s, _ in states(db)} == {turn_state.ANSWERED}


# --- shutdown ------------------------------------------------------------------------------------------


async def test_sigterm_with_a_turn_in_flight_finishes_within_the_deadline_and_keeps_the_message_pending(
    db, world, stoppable, monkeypatch
):
    async def hanging_turn(db, conversation, contact, instance, text, received_at=None, **kwargs):
        world["turns"].append(text)
        await asyncio.Event().wait()

    monkeypatch.setattr(executor, "handle_incoming", hanging_turn)
    monkeypatch.setattr(settings, "SHUTDOWN_TIMEOUT_SECONDS", 0.2)
    consumer = WhatsAppMessageConsumer()
    await consumer.process_webhook_event(upsert(text="Oi"))
    await asyncio.sleep(0.05)

    started = asyncio.get_running_loop().time()
    await asyncio.wait_for(consumer.stop(), timeout=3)
    assert asyncio.get_running_loop().time() - started < 1.5

    assert states(db) == [("Oi", turn_state.PENDING, turn_state.RELEASED)]
    assert world["sent"] == [] and not consumer.runner.tasks

    async def fresh_turn(db, conversation, contact, instance, text, received_at=None, **kwargs):
        return TurnResult(reply_text="Resposta")

    monkeypatch.setattr(executor, "handle_incoming", fresh_turn)
    successor = WhatsAppMessageConsumer()
    assert await successor.recovery.sweep() == 1  # o RELEASED é retomado sem esperar a posse vencer
    await successor.drain()
    assert len(world["sent"]) == 1


async def test_shutdown_lets_a_turn_that_fits_the_deadline_finish(db, world, stoppable, monkeypatch):
    async def short_turn(db, conversation, contact, instance, text, received_at=None, **kwargs):
        await asyncio.sleep(0.05)
        return TurnResult(reply_text="Resposta")

    monkeypatch.setattr(executor, "handle_incoming", short_turn)
    consumer = WhatsAppMessageConsumer()
    await consumer.process_webhook_event(upsert(text="Oi"))
    await asyncio.sleep(0)

    await consumer.stop()

    assert len(world["sent"]) == 1
    assert states(db) == [("Oi", turn_state.ANSWERED, turn_state.REPLIED)]


async def test_shutdown_returns_messages_still_waiting_for_the_debounce(db, world, stoppable, monkeypatch):
    monkeypatch.setattr(settings, "DEBOUNCE_SECONDS", 30.0)
    monkeypatch.setattr(settings, "SHUTDOWN_TIMEOUT_SECONDS", 0.1)
    consumer = WhatsAppMessageConsumer()
    await consumer.process_webhook_event(upsert(text="Oi"))
    await asyncio.sleep(0.02)

    await consumer.stop()

    row = incoming(db)[0]
    assert (row.turn_state, row.turn_reason, row.turn_claimed_at) == (turn_state.PENDING, turn_state.QUEUED, None)
    successor = WhatsAppMessageConsumer()
    assert await successor.recovery.sweep() == 1
    await successor.drain()
    assert len(world["sent"]) == 1
