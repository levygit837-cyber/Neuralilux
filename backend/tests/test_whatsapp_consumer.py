"""Consumer do webhook da Evolution: filtros antes do Agent, mídia, eco, Instance desconhecida e concorrência."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.agent import executor
from app.agent.loop import TurnResult
from app.models import Agent, BusinessType, Company, Contact, Conversation, Instance, Message
from app.whatsapp.evolution_client import evolution_api
from app.whatsapp import consumer as consumer_module
from app.realtime.event_bus import realtime_event_bus
from app.whatsapp.consumer import MEDIA_REPLY, WhatsAppMessageConsumer, parse_content
from tests.conftest import TestingSessionLocal

JID = "5511999990001@s.whatsapp.net"


def _now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def upsert(*, text="Oi", remote_jid=JID, message_id="in-1", from_me=False, ts=None, message=None, key_extra=None, instance="evo-t7"):
    key = {"remoteJid": remote_jid, "fromMe": from_me, "id": message_id, **(key_extra or {})}
    return {
        "event": "messages.upsert",
        "data": {
            "instance": instance,
            "data": {
                "key": key,
                "message": message if message is not None else {"conversation": text},
                "pushName": "Contato",
                "messageTimestamp": ts if ts is not None else _now(),
            },
        },
    }


@pytest.fixture
def world(db, monkeypatch):
    """Company com Agent e Instance ligada; Turn, envio e Summary são falsos e registrados."""
    business_type = BusinessType(name="Restaurante", slug="restaurant")
    db.add(business_type)
    db.flush()
    company = Company(name="Pizzaria", business_type_id=business_type.id)
    db.add(company)
    db.flush()
    agent = Agent(name="Atendente", system_prompt="", company_id=company.id, is_active=True)
    db.add(agent)
    db.flush()
    instance = Instance(
        name="evo-t7", evolution_instance_id="evo-t7", company_id=company.id, agent_id=agent.id, agent_enabled=True
    )
    db.add(instance)
    db.commit()

    calls = {"turns": [], "sent": [], "summaries": []}
    sent_ids = iter(f"out-{n}" for n in range(1, 100))

    async def fake_handle_incoming(db, conversation, contact, instance, text):
        calls["turns"].append(text)
        return TurnResult(reply_text="Resposta")

    async def fake_send(*, instance_name, remote_jid, text):
        calls["sent"].append({"instance_name": instance_name, "remote_jid": remote_jid, "text": text})
        return {"key": {"id": next(sent_ids)}}

    async def fake_refresh(conversation_id):
        calls["summaries"].append(conversation_id)

    monkeypatch.setattr(executor, "handle_incoming", fake_handle_incoming)
    monkeypatch.setattr(executor, "refresh_summary", fake_refresh)
    monkeypatch.setattr(evolution_api, "send_text_message", fake_send)
    monkeypatch.setattr(consumer_module, "SessionLocal", TestingSessionLocal)
    calls.update(company=company, agent=agent, instance=instance)
    return calls


async def process(consumer: WhatsAppMessageConsumer, payload: dict) -> None:
    await consumer.process_webhook_event(payload)
    await consumer.drain()


def messages(db) -> list[Message]:
    db.expire_all()
    return db.query(Message).order_by(Message.created_at, Message.message_id).all()


# --- Instance desconhecida -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_instance_is_discarded_and_nothing_is_created(db, world):
    await process(WhatsAppMessageConsumer(), upsert(instance="evo-desconhecida"))

    assert db.query(Instance).filter(Instance.evolution_instance_id == "evo-desconhecida").count() == 0
    assert db.query(Message).count() == 0 and db.query(Contact).count() == 0
    assert world["turns"] == [] and world["sent"] == []


@pytest.mark.asyncio
async def test_connection_update_for_unknown_instance_does_not_create_one(db, world):
    payload = {"event": "connection.update", "data": {"instance": "evo-desconhecida", "data": {"state": "open"}}}

    await process(WhatsAppMessageConsumer(), payload)

    assert db.query(Instance).filter(Instance.evolution_instance_id == "evo-desconhecida").count() == 0


# --- Filtros antes do Agent --------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("jid", ["553388773141-1562969789@g.us", "status@broadcast", "5511999@broadcast"])
async def test_group_and_broadcast_messages_never_reach_the_agent_or_the_database(db, world, jid):
    await process(WhatsAppMessageConsumer(), upsert(remote_jid=jid))

    assert world["turns"] == [] and world["sent"] == []
    assert db.query(Message).count() == 0 and db.query(Conversation).count() == 0


@pytest.mark.asyncio
async def test_from_me_message_is_stored_but_the_agent_stays_silent(db, world):
    await process(WhatsAppMessageConsumer(), upsert(from_me=True, message_id="mine-1"))

    [stored] = messages(db)
    assert (stored.is_from_me, stored.direction) == (True, "outgoing")
    assert world["turns"] == [] and world["sent"] == []


@pytest.mark.asyncio
async def test_message_older_than_five_minutes_before_consumer_start_is_stored_but_not_answered(db, world):
    consumer = WhatsAppMessageConsumer()
    old = int((consumer._started_at - timedelta(minutes=5, seconds=30)).timestamp())

    await process(consumer, upsert(ts=old))

    assert len(messages(db)) == 1
    assert world["turns"] == [] and world["sent"] == []


@pytest.mark.asyncio
async def test_message_within_five_minutes_of_consumer_start_is_answered(db, world):
    consumer = WhatsAppMessageConsumer()
    recent = int((consumer._started_at - timedelta(minutes=4)).timestamp())

    await process(consumer, upsert(ts=recent))

    assert world["turns"] == ["Oi"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key_extra",
    [{"remoteJidAlt": "5511988887777@s.whatsapp.net"}, {"senderPn": "5511988887777@s.whatsapp.net"}],
)
async def test_lid_jid_is_resolved_to_the_real_number_and_answered_there(db, world, key_extra):
    await process(WhatsAppMessageConsumer(), upsert(remote_jid="123456789012@lid", key_extra=key_extra))

    [stored, reply] = messages(db)
    assert stored.remote_jid == "5511988887777@s.whatsapp.net"
    assert db.query(Contact).one().phone_number == "5511988887777"
    assert world["sent"][0]["remote_jid"] == "5511988887777@s.whatsapp.net"


@pytest.mark.asyncio
async def test_lid_without_a_real_number_is_stored_but_not_answered(db, world):
    await process(WhatsAppMessageConsumer(), upsert(remote_jid="123456789012@lid"))

    assert len(messages(db)) == 1
    assert world["turns"] == [] and world["sent"] == []


# --- Mídia sem texto ------------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        {"imageMessage": {"mimetype": "image/jpeg"}},
        {"audioMessage": {"mimetype": "audio/ogg"}},
        {"documentMessage": {"fileName": "a.pdf"}},
        {"stickerMessage": {"mimetype": "image/webp"}},
        {"ephemeralMessage": {"message": {"imageMessage": {}}}},
    ],
)
async def test_media_without_text_gets_the_fixed_reply_without_calling_the_model(db, world, message):
    await process(WhatsAppMessageConsumer(), upsert(message=message))

    assert world["turns"] == []
    assert [sent["text"] for sent in world["sent"]] == [MEDIA_REPLY]


@pytest.mark.asyncio
async def test_media_with_a_caption_is_handled_as_text(db, world):
    await process(WhatsAppMessageConsumer(), upsert(message={"imageMessage": {"caption": "Quero esta pizza"}}))

    assert world["turns"] == ["Quero esta pizza"]


@pytest.mark.asyncio
async def test_media_reply_is_not_sent_during_handoff(db, world):
    await process(WhatsAppMessageConsumer(), upsert(message_id="seed-1"))  # cria a Conversation
    db.query(Conversation).update({"human_in_loop": True})
    db.commit()
    world["sent"].clear()

    await process(WhatsAppMessageConsumer(), upsert(message={"audioMessage": {}}, message_id="audio-1"))

    assert world["sent"] == []


# --- Resposta persistida e eco deduplicado ---------------------------------------------------------


@pytest.mark.asyncio
async def test_bot_reply_is_stored_as_from_me_with_the_evolution_id(db, world):
    await process(WhatsAppMessageConsumer(), upsert())

    reply = db.query(Message).filter(Message.message_id == "out-1").one()
    assert (reply.is_from_me, reply.direction, reply.content, reply.status) == (True, "outgoing", "Resposta", "sent")
    conversation = db.query(Conversation).one()
    assert reply.conversation_id == conversation.id
    assert conversation.last_message_preview == "Resposta"
    assert conversation.unread_count == 1  # só a mensagem do Contact conta


@pytest.mark.asyncio
async def test_webhook_echo_of_the_reply_is_deduplicated_and_does_not_trigger_the_agent(db, world):
    consumer = WhatsAppMessageConsumer()
    await process(consumer, upsert())

    await process(consumer, upsert(text="Resposta", from_me=True, message_id="out-1"))

    assert [m.message_id for m in messages(db)].count("out-1") == 1
    assert len(messages(db)) == 2
    assert world["turns"] == ["Oi"] and len(world["sent"]) == 1


@pytest.mark.asyncio
async def test_redelivered_incoming_message_is_answered_once(db, world):
    consumer = WhatsAppMessageConsumer()

    await process(consumer, upsert())
    await process(consumer, upsert())

    assert world["turns"] == ["Oi"] and len(world["sent"]) == 1


@pytest.mark.asyncio
async def test_reply_without_an_evolution_id_is_left_to_the_echo(db, world, monkeypatch):
    async def send_without_id(**_kwargs):
        return {"status": "ok"}

    monkeypatch.setattr(evolution_api, "send_text_message", send_without_id)
    consumer = WhatsAppMessageConsumer()

    await process(consumer, upsert())
    assert len(messages(db)) == 1  # nada gravado sem id

    await process(consumer, upsert(text="Resposta", from_me=True, message_id="echo-9"))
    assert sorted(m.message_id for m in messages(db)) == ["echo-9", "in-1"]


@pytest.mark.asyncio
async def test_failure_to_persist_the_reply_does_not_break_the_turn(db, world, monkeypatch):
    async def send_with_colliding_id(*, instance_name, remote_jid, text):
        world["sent"].append(text)
        return {"key": {"id": "in-1"}}  # já existe: o commit da resposta viola a unicidade de message_id

    monkeypatch.setattr(evolution_api, "send_text_message", send_with_colliding_id)
    consumer = WhatsAppMessageConsumer()

    await process(consumer, upsert(message_id="in-1"))  # a resposta já saiu; o erro só vai para o log

    assert world["sent"] == ["Resposta"]
    assert [m.message_id for m in messages(db)] == ["in-1"]  # Session continua usável, nada pela metade
    await process(consumer, upsert(message_id="in-2"))
    assert len(world["sent"]) == 2


# --- Agent da Instance / Company ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_instance_without_binding_uses_the_agent_of_its_company_and_binds_it(db, world):
    db.query(Instance).update({"agent_id": None})
    db.commit()

    await process(WhatsAppMessageConsumer(), upsert())

    assert world["turns"] == ["Oi"]
    assert db.query(Instance).one().agent_id == world["agent"].id


@pytest.mark.asyncio
async def test_agent_of_another_company_is_never_used(db, world):
    other = Company(name="Outra")
    db.add(other)
    db.flush()
    db.add(Agent(name="Alheio", system_prompt="", company_id=other.id, is_active=True))
    db.query(Agent).filter(Agent.id == world["agent"].id).update({"is_active": False})
    db.query(Instance).update({"agent_id": None})
    db.commit()

    await process(WhatsAppMessageConsumer(), upsert())

    assert world["turns"] == [] and world["sent"] == []
    assert db.query(Instance).one().agent_id is None


@pytest.mark.asyncio
async def test_missing_agent_logs_one_clear_error_and_never_answers(db, world, monkeypatch):
    db.query(Agent).delete()
    db.query(Instance).update({"agent_id": None})
    db.commit()
    errors = []
    monkeypatch.setattr(consumer_module.logger, "bind", lambda **_: type("L", (), {
        "info": lambda *a, **k: None,
        "error": lambda self, msg, **k: errors.append(msg),
        "exception": lambda *a, **k: None,
    })())
    consumer = WhatsAppMessageConsumer()

    await process(consumer, upsert(message_id="in-1"))
    await process(consumer, upsert(message_id="in-2"))

    assert len(errors) == 1 and "Agent" in errors[0]
    assert world["turns"] == [] and world["sent"] == []


@pytest.mark.asyncio
async def test_disabled_agent_does_not_answer(db, world):
    db.query(Instance).update({"agent_enabled": False})
    db.commit()

    await process(WhatsAppMessageConsumer(), upsert())

    assert world["turns"] == [] and len(messages(db)) == 1


# --- Concorrência ----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_messages_of_one_conversation_run_in_order_and_never_overlap(db, world, monkeypatch):
    running, overlaps, order = 0, [], []

    async def slow_turn(db, conversation, contact, instance, text):
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

    async def rendezvous_turn(db, conversation, contact, instance, text):
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
