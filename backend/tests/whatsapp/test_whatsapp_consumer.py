"""Consumer do webhook da Evolution: filtros antes do Agent, mídia, eco, Instance desconhecida e Agent."""
from datetime import timedelta

import pytest

from app.models import Agent, Company, Contact, Conversation, Instance, Message
from app.whatsapp import consumer as consumer_module
from app.whatsapp.consumer import WhatsAppMessageConsumer
from app.whatsapp import turn_runner as turn_runner_module
from app.whatsapp.turn_runner import MEDIA_REPLY
from app.whatsapp.evolution_client import evolution_api
from consumer_helpers import messages, process, upsert


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
@pytest.mark.parametrize("jid", ["status@broadcast", "5511999@broadcast"])
async def test_broadcast_messages_never_reach_the_agent_or_the_database(db, world, jid):
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
async def test_reply_without_an_evolution_id_is_adopted_by_the_echo(db, world, monkeypatch):
    async def send_without_id(**_kwargs):
        return {"status": "ok"}

    monkeypatch.setattr(evolution_api, "send_text_message", send_without_id)
    consumer = WhatsAppMessageConsumer()

    await process(consumer, upsert())
    assert sorted((m.message_id or "", m.content) for m in messages(db)) == [("", "Resposta"), ("in-1", "Oi")]  # gravada sem id

    await process(consumer, upsert(text="Resposta", from_me=True, message_id="echo-9"))
    assert sorted((m.message_id, m.content) for m in messages(db)) == [("echo-9", "Resposta"), ("in-1", "Oi")]
    assert world["turns"] == ["Oi"]


@pytest.mark.asyncio
async def test_two_identical_replies_without_an_id_are_each_adopted_by_their_own_echo(db, world, monkeypatch):
    async def send_without_id(**_kwargs):
        return {"status": "ok"}

    monkeypatch.setattr(evolution_api, "send_text_message", send_without_id)
    consumer = WhatsAppMessageConsumer()

    await process(consumer, upsert(message_id="in-1"))
    await process(consumer, upsert(message_id="in-2"))  # segunda resposta, mesmo texto, menos de 2 min depois
    assert sorted(m.message_id or "" for m in messages(db) if m.is_from_me) == ["", ""]

    await process(consumer, upsert(text="Resposta", from_me=True, message_id="echo-1"))
    await process(consumer, upsert(text="Resposta", from_me=True, message_id="echo-2"))

    assert sorted(m.message_id for m in messages(db)) == ["echo-1", "echo-2", "in-1", "in-2"]  # nenhuma Message nova
    assert world["turns"] == ["Oi", "Oi"]


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
async def test_instance_without_binding_uses_the_agent_of_its_company_without_writing_the_binding(db, world):
    db.query(Instance).update({"agent_id": None})
    db.commit()

    await process(WhatsAppMessageConsumer(), upsert())

    assert world["turns"] == ["Oi"]
    assert db.query(Instance).one().agent_id is None  # ler o Agent do Turn não grava vínculo


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
    monkeypatch.setattr(turn_runner_module.logger, "bind", lambda **_: type("L", (), {
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

    assert world["turns"] == [] and world["sent"] == [] and len(messages(db)) == 1


# --- Concorrência ----------------------------------------------------------------------------------
