"""Session de atendimento (ADR 0007): quando abre, o que a Recent Window mostra e o que continua alcançável."""

from datetime import datetime, timedelta, timezone

import pytest

from app.agent import memory, sessions
from app.agent.contracts import MessagesResponse
from app.models import Company, ConversationMemorySummary, Message
from tests.agent_fakes import FakePack

T0 = datetime(2026, 10, 21, 18, 0, tzinfo=timezone.utc)


class RecordingPack(FakePack):
    def __init__(self):
        super().__init__("registro", [])
        self.started: list[str] = []

    def on_session_start(self, db, conversation) -> None:
        self.started.append(conversation.id)


@pytest.fixture
def company(db):
    company = Company(name="Pizzaria")
    db.add(company)
    db.commit()
    return company


@pytest.fixture
def add_message(db):
    def _add(conversation, at, role="user", content="oi"):
        message = Message(
            instance_id=conversation.instance_id,
            conversation_id=conversation.id,
            remote_jid=conversation.remote_jid,
            message_type="text",
            content=content,
            direction="incoming" if role == "user" else "outgoing",
            timestamp=at,
        )
        db.add(message)
        conversation.last_message_at = at
        db.commit()
        return message

    return _add


def test_first_message_of_a_conversation_opens_its_session(db, conversation_factory, company):
    conversation = conversation_factory("conv-first")

    opened = sessions.roll_session(db, conversation, company, [], T0)

    assert opened is False
    assert conversation.session_started_at == T0


def test_message_exactly_at_the_limit_continues_and_one_second_later_opens_a_new_session(
    db, conversation_factory, company
):
    conversation = conversation_factory("conv-limit")
    sessions.roll_session(db, conversation, company, [], T0)
    conversation.last_message_at = T0

    at_limit = T0 + timedelta(hours=3)
    assert sessions.roll_session(db, conversation, company, [], at_limit) is False
    assert conversation.session_started_at == T0

    after_limit = at_limit + timedelta(seconds=1)
    assert sessions.roll_session(db, conversation, company, [], after_limit) is True
    assert conversation.session_started_at == after_limit


def test_limit_is_configurable_per_company(db, conversation_factory, company):
    company.session_timeout_minutes = 30
    conversation = conversation_factory("conv-custom")
    sessions.roll_session(db, conversation, company, [], T0)
    conversation.last_message_at = T0

    assert sessions.roll_session(db, conversation, company, [], T0 + timedelta(minutes=29)) is False
    assert sessions.roll_session(db, conversation, company, [], T0 + timedelta(minutes=31)) is True


def test_new_company_defaults_to_three_hours(db, company):
    assert company.session_timeout_minutes == 180


def test_naive_datetimes_from_the_database_are_compared_as_utc(db, conversation_factory, company):
    conversation = conversation_factory("conv-naive")
    conversation.last_message_at = T0.replace(tzinfo=None)

    assert sessions.roll_session(db, conversation, company, [], T0 + timedelta(hours=3, minutes=1)) is True


def test_expired_session_notifies_every_pack_and_a_continued_one_does_not(db, conversation_factory, company):
    conversation = conversation_factory("conv-hook")
    pack = RecordingPack()
    sessions.roll_session(db, conversation, company, [pack], T0)
    conversation.last_message_at = T0

    sessions.roll_session(db, conversation, company, [pack], T0 + timedelta(hours=1))
    assert pack.started == []

    sessions.roll_session(db, conversation, company, [pack], T0 + timedelta(hours=5))
    assert pack.started == [conversation.id]


def test_a_late_backlog_message_does_not_open_a_session(db, conversation_factory, company):
    conversation = conversation_factory("conv-backlog")
    sessions.roll_session(db, conversation, company, [], T0)
    conversation.last_message_at = T0 + timedelta(hours=10)

    assert sessions.roll_session(db, conversation, company, [], T0 + timedelta(hours=1)) is False
    assert conversation.session_started_at == T0


def test_recent_window_has_only_messages_of_the_current_session(db, conversation_factory, add_message):
    conversation = conversation_factory("conv-window")
    add_message(conversation, T0, content="quero uma toscana")
    add_message(conversation, T0 + timedelta(minutes=1), role="assistant", content="anotado")
    conversation.session_started_at = T0 + timedelta(hours=7)
    add_message(conversation, T0 + timedelta(hours=7), content="boa noite")
    db.commit()

    _, history = memory.build_context(db, conversation)

    assert history == [{"role": "user", "content": "boa noite"}]


def test_conversation_without_a_recorded_session_keeps_the_whole_window(db, conversation_factory, add_message):
    conversation = conversation_factory("conv-legacy")
    add_message(conversation, T0, content="antiga")
    add_message(conversation, T0 + timedelta(minutes=1), role="assistant", content="resposta")

    _, history = memory.build_context(db, conversation)

    assert [m["content"] for m in history] == ["antiga", "resposta"]


def test_history_search_and_summary_still_reach_previous_sessions(db, conversation_factory, add_message):
    conversation = conversation_factory("conv-memory")
    add_message(conversation, T0, content="quero a pizza toscana de sempre")
    conversation.session_started_at = T0 + timedelta(hours=7)
    add_message(conversation, T0 + timedelta(hours=7), content="boa noite")
    db.add(ConversationMemorySummary(conversation_id=conversation.id, summary="Pediu toscana.",
                                     covered_until_message_id=db.query(Message.id).first()[0], message_count=1))
    db.commit()

    summary, history = memory.build_context(db, conversation)
    found = memory.search_history(db, conversation.contact_id, conversation.instance_id, "toscana")

    assert summary == "Pediu toscana."
    assert [h["content"] for h in history] == ["boa noite"]
    assert [f["snippet"] for f in found] == ["quero a pizza toscana de sempre"]


class _Client:
    def __init__(self):
        self.prompts: list[str] = []

    async def create(self, request):
        self.prompts.append(request.messages[0]["content"])
        return MessagesResponse(
            content=[{"type": "text", "text": "Resumo novo."}], stop_reason="end_turn", model="fake", output_tokens=5
        )


@pytest.mark.asyncio
async def test_messages_of_a_previous_session_count_as_outside_the_window_for_the_summary(
    db, conversation_factory, add_message
):
    conversation = conversation_factory("conv-summary")
    for n in range(20):
        add_message(conversation, T0 + timedelta(minutes=n), role="user" if n % 2 == 0 else "assistant",
                    content=f"antiga {n}")
    conversation.session_started_at = T0 + timedelta(hours=7)
    add_message(conversation, T0 + timedelta(hours=7), content="boa noite")
    db.commit()
    client = _Client()

    await memory.maybe_refresh_summary(db, client, "fake", conversation)

    assert len(client.prompts) == 1
    assert "antiga 0" in client.prompts[0] and "antiga 19" in client.prompts[0]
    assert "boa noite" not in client.prompts[0]
    assert db.get(ConversationMemorySummary, conversation.id).summary == "Resumo novo."
