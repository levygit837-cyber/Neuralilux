"""O consumer abre a Session de atendimento quando a Message do Contact chega depois do limite (ADR 0007)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import Contact, Conversation, CustomerOrder
from app.whatsapp import consumer as consumer_module
from app.whatsapp.consumer import WhatsAppMessageConsumer
from consumer_helpers import JID, messages, process, upsert

pytestmark = pytest.mark.asyncio


def _ts(moment: datetime) -> int:
    return int(moment.timestamp())


@pytest.fixture
def consumer():
    instance = WhatsAppMessageConsumer()
    instance._started_at = datetime.now(timezone.utc) - timedelta(days=2)  # nenhuma Message é backlog
    return instance


def _conversation(db) -> Conversation:
    db.expire_all()
    return db.query(Conversation).one()


def _replied_at(db, moment: datetime) -> None:
    """A resposta do Agent leva o relógio real; recoloca a última Message no instante simulado."""
    conversation = db.query(Conversation).one()
    conversation.last_message_at = moment
    db.commit()


def _open_order(db, conversation) -> CustomerOrder:
    contact = db.query(Contact).one()
    order = CustomerOrder(
        order_number="T-1",
        conversation_id=conversation.id,
        instance_id=conversation.instance_id,
        contact_id=contact.id,
        remote_jid=JID,
        status="open",
    )
    db.add(order)
    db.commit()
    return order


async def test_first_message_starts_the_session_at_its_own_timestamp(db, world, consumer):
    first = datetime.now(timezone.utc) - timedelta(hours=1)

    await process(consumer, upsert(message_id="m1", ts=_ts(first)))

    started = _conversation(db).session_started_at
    assert abs(started.replace(tzinfo=timezone.utc) - first) < timedelta(seconds=2)


async def test_message_within_the_limit_keeps_the_session_and_the_open_order(db, world, consumer):
    t0 = datetime.now(timezone.utc) - timedelta(hours=5)
    await process(consumer, upsert(message_id="m1", ts=_ts(t0)))
    _replied_at(db, t0)
    order = _open_order(db, _conversation(db))
    started = _conversation(db).session_started_at

    await process(consumer, upsert(message_id="m2", ts=_ts(t0 + timedelta(hours=2, minutes=59))))

    assert _conversation(db).session_started_at == started
    db.refresh(order)
    assert order.status == "open"


async def test_message_after_the_limit_opens_a_new_session_and_abandons_the_open_order(db, world, consumer):
    t0 = datetime.now(timezone.utc) - timedelta(hours=8)
    await process(consumer, upsert(message_id="m1", ts=_ts(t0)))
    _replied_at(db, t0)
    order = _open_order(db, _conversation(db))
    later = t0 + timedelta(hours=7)

    await process(consumer, upsert(message_id="m2", ts=_ts(later)))

    started = _conversation(db).session_started_at.replace(tzinfo=timezone.utc)
    assert abs(started - later) < timedelta(seconds=2)
    db.refresh(order)
    assert order.status == "abandoned"
    assert world["turns"] == ["Oi", "Oi"]


async def test_limit_comes_from_the_company(db, world, consumer):
    world["company"].session_timeout_minutes = 20
    db.commit()
    t0 = datetime.now(timezone.utc) - timedelta(hours=1)
    await process(consumer, upsert(message_id="m1", ts=_ts(t0)))
    _replied_at(db, t0)
    order = _open_order(db, _conversation(db))

    await process(consumer, upsert(message_id="m2", ts=_ts(t0 + timedelta(minutes=19))))
    _replied_at(db, t0 + timedelta(minutes=19))
    db.refresh(order)
    assert order.status == "open"

    await process(consumer, upsert(message_id="m3", ts=_ts(t0 + timedelta(minutes=19 + 21))))
    db.refresh(order)
    assert order.status == "abandoned"


async def test_our_own_reply_after_a_long_pause_does_not_open_a_session(db, world, consumer):
    t0 = datetime.now(timezone.utc) - timedelta(hours=8)
    await process(consumer, upsert(message_id="m1", ts=_ts(t0)))
    _replied_at(db, t0)
    order = _open_order(db, _conversation(db))
    started = _conversation(db).session_started_at

    await process(consumer, upsert(message_id="out-x", from_me=True, ts=_ts(t0 + timedelta(hours=7))))

    assert _conversation(db).session_started_at == started
    db.refresh(order)
    assert order.status == "open"


class PackWithoutHook:
    name = "sem-gancho"

    def tools(self):
        return []

    def system_prompt_section(self, ctx) -> str:
        return ""

    def turn_context(self, ctx) -> str:
        return ""


async def test_pack_without_the_session_hook_still_gets_the_message_saved_and_the_turn_run(
    db, world, consumer, monkeypatch
):
    monkeypatch.setattr(consumer_module, "packs_for", lambda company: [PackWithoutHook()])
    t0 = datetime.now(timezone.utc) - timedelta(hours=8)
    await process(consumer, upsert(message_id="m1", ts=_ts(t0)))
    _replied_at(db, t0)
    later = t0 + timedelta(hours=7)

    await process(consumer, upsert(message_id="m2", text="Voltei", ts=_ts(later)))

    assert "Voltei" in [m.content for m in messages(db)]
    assert world["turns"] == ["Oi", "Voltei"]
    started = _conversation(db).session_started_at.replace(tzinfo=timezone.utc)
    assert abs(started - later) < timedelta(seconds=2)
