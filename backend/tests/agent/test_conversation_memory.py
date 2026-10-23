"""Memória por Conversation: Recent Window, Summary e History Search (ADR 0003)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.agent import memory
from app.agent.contracts import MessagesResponse
from app.models import Message

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def add_message(db):
    """Grava uma Message de texto; `n` define a ordem cronológica."""
    def _add(conversation, n, role="user", content=None, message_type="text"):
        message = Message(
            instance_id=conversation.instance_id,
            conversation_id=conversation.id,
            remote_jid=conversation.remote_jid,
            message_type=message_type,
            content=content if content is not None else f"msg {n}",
            direction="incoming" if role == "user" else "outgoing",
            is_from_me=role == "assistant",
            timestamp=T0 + timedelta(minutes=n),
        )
        db.add(message)
        db.commit()
        return message

    return _add


def test_build_context_returns_only_the_last_window_in_order(db, conversation_factory, add_message):
    conversation = conversation_factory("conv-window")
    for n in range(1, 31):
        add_message(conversation, n, role="user" if n % 2 else "assistant", content=f"msg {n}")

    summary, history = memory.build_context(db, conversation, window=20)

    assert summary is None
    # 30 mensagens alternadas; a janela de 20 começa em msg 11 (user).
    assert history[0] == {"role": "user", "content": "msg 11"}
    assert history[-1] == {"role": "assistant", "content": "msg 30"}
    assert len(history) == 20


def test_build_context_merges_consecutive_messages_of_the_same_role(db, conversation_factory, add_message):
    conversation = conversation_factory("conv-merge")
    add_message(conversation, 1, "user", "oi")
    add_message(conversation, 2, "user", "quero uma pizza")
    add_message(conversation, 3, "assistant", "claro")
    add_message(conversation, 4, "assistant", "qual sabor?")
    add_message(conversation, 5, "user", "toscana")

    _, history = memory.build_context(db, conversation)

    assert history == [
        {"role": "user", "content": "oi\nquero uma pizza"},
        {"role": "assistant", "content": "claro\nqual sabor?"},
        {"role": "user", "content": "toscana"},
    ]


def test_build_context_starts_with_a_user_message(db, conversation_factory, add_message):
    conversation = conversation_factory("conv-first-user")
    add_message(conversation, 1, "assistant", "bem-vindo")
    add_message(conversation, 2, "assistant", "como posso ajudar?")
    add_message(conversation, 3, "user", "cardápio")
    add_message(conversation, 4, "assistant", "aqui está")

    _, history = memory.build_context(db, conversation)

    assert history == [
        {"role": "user", "content": "cardápio"},
        {"role": "assistant", "content": "aqui está"},
    ]


def test_build_context_ignores_media_and_empty_messages(db, conversation_factory, add_message):
    conversation = conversation_factory("conv-text-only")
    add_message(conversation, 1, "user", "olha a foto", message_type="image")
    add_message(conversation, 2, "user", "", message_type="text")
    add_message(conversation, 3, "user", "bom dia")

    _, history = memory.build_context(db, conversation)

    assert history == [{"role": "user", "content": "bom dia"}]


class FakeClient:
    """MessagesClient que devolve um texto fixo e guarda as requests."""

    def __init__(self, text="Cliente pediu pizza toscana.", error=None):
        self.text = text
        self.error = error
        self.requests = []

    async def create(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return MessagesResponse(
            content=[{"type": "text", "text": self.text}],
            stop_reason="end_turn",
            model=request.model,
            output_tokens=10,
        )


def _fill(conversation, add_message, count):
    return [
        add_message(conversation, n, "user" if n % 2 else "assistant", f"msg {n}")
        for n in range(1, count + 1)
    ]


@pytest.mark.asyncio
async def test_summary_is_not_generated_below_twenty_messages_outside_the_window(
    db, conversation_factory, add_message
):
    conversation = conversation_factory("conv-sum-below")
    _fill(conversation, add_message, 39)  # 19 fora da janela de 20
    client = FakeClient()

    await memory.maybe_refresh_summary(db, client, "modelo-x", conversation)

    assert client.requests == []
    assert memory.build_context(db, conversation)[0] is None


@pytest.mark.asyncio
async def test_summary_is_generated_with_twenty_messages_outside_the_window(
    db, conversation_factory, add_message
):
    conversation = conversation_factory("conv-sum-at")
    _fill(conversation, add_message, 40)
    client = FakeClient()

    await memory.maybe_refresh_summary(db, client, "modelo-x", conversation)

    assert len(client.requests) == 1
    request = client.requests[0]
    assert request.model == "modelo-x"
    assert request.effort == "low"
    prompt = request.messages[0]["content"]
    assert "Cliente: msg 1" in prompt.splitlines()
    assert "msg 20" in prompt
    assert "msg 21" not in prompt  # msg 21 em diante é a Recent Window
    summary, history = memory.build_context(db, conversation)
    assert summary == "Cliente pediu pizza toscana."
    assert history[0] == {"role": "user", "content": "msg 21"}


@pytest.mark.asyncio
async def test_summary_is_not_regenerated_until_twenty_new_messages_leave_the_window(
    db, conversation_factory, add_message
):
    conversation = conversation_factory("conv-sum-again")
    _fill(conversation, add_message, 40)
    client = FakeClient(text="Primeiro resumo.")
    await memory.maybe_refresh_summary(db, client, "modelo-x", conversation)

    for n in range(41, 60):  # 19 novas saem da janela: ainda não dispara
        add_message(conversation, n, "user" if n % 2 else "assistant", f"msg {n}")
    await memory.maybe_refresh_summary(db, client, "modelo-x", conversation)
    assert len(client.requests) == 1

    add_message(conversation, 60, "assistant", "msg 60")  # a 20ª nova
    client.text = "Segundo resumo."
    await memory.maybe_refresh_summary(db, client, "modelo-x", conversation)

    assert len(client.requests) == 2
    second_prompt = client.requests[1].messages[0]["content"]
    assert "Primeiro resumo." in second_prompt
    assert "msg 21" in second_prompt and "msg 40" in second_prompt
    assert "Cliente: msg 1" not in second_prompt.splitlines()  # já estava no primeiro resumo
    assert "msg 20" not in second_prompt
    assert memory.build_context(db, conversation)[0] == "Segundo resumo."


@pytest.mark.asyncio
async def test_summary_is_capped_at_1200_characters(db, conversation_factory, add_message):
    conversation = conversation_factory("conv-sum-cap")
    _fill(conversation, add_message, 40)

    await memory.maybe_refresh_summary(db, FakeClient(text="a" * 3000), "modelo-x", conversation)

    assert len(memory.build_context(db, conversation)[0]) <= 1200


@pytest.mark.asyncio
async def test_summary_failure_is_only_logged(db, conversation_factory, add_message, caplog):
    conversation = conversation_factory("conv-sum-fail")
    _fill(conversation, add_message, 40)

    await memory.maybe_refresh_summary(
        db, FakeClient(error=RuntimeError("gateway fora do ar")), "modelo-x", conversation
    )

    assert memory.build_context(db, conversation)[0] is None
    assert "gateway fora do ar" in caplog.text


def _second_conversation(db, conversation, conversation_id):
    """Outra Conversation do mesmo Contact na mesma Instance."""
    from app.models import Conversation

    other = Conversation(
        id=conversation_id,
        instance_id=conversation.instance_id,
        contact_id=conversation.contact_id,
        remote_jid=conversation.remote_jid,
    )
    db.add(other)
    db.commit()
    return other


def test_search_history_finds_old_messages_across_the_contact_conversations(
    db, conversation_factory, add_message
):
    first = conversation_factory("conv-search-a")
    second = _second_conversation(db, first, "conv-search-b")
    add_message(first, 1, "user", "Quero uma pizza toscana grande")
    add_message(first, 2, "assistant", "Anotado: pizza toscana grande")
    add_message(second, 3, "user", "Vocês abrem domingo?")

    hits = memory.search_history(db, first.contact_id, first.instance_id, "toscana")

    assert [(h["role"], h["snippet"]) for h in hits] == [
        ("assistant", "Anotado: pizza toscana grande"),
        ("user", "Quero uma pizza toscana grande"),
    ]
    assert hits[0]["date"].startswith("2026-10-01")

    cross = memory.search_history(db, first.contact_id, first.instance_id, "domingo")
    assert [h["snippet"] for h in cross] == ["Vocês abrem domingo?"]


def test_search_history_never_returns_other_contacts_or_instances(
    db, conversation_factory, add_message
):
    mine = conversation_factory("conv-scope-mine", "5511111111111@s.whatsapp.net")
    other_contact = conversation_factory("conv-scope-other", "5511222222222@s.whatsapp.net")
    # Mesmo número em outra Instance também é outro Contact.
    other_instance = conversation_factory("conv-scope-inst", "5511111111111@s.whatsapp.net")
    add_message(mine, 1, "user", "pizza de calabresa")
    add_message(other_contact, 2, "user", "pizza de calabresa do outro cliente")
    add_message(other_instance, 3, "user", "pizza de calabresa em outra instância")

    hits = memory.search_history(db, mine.contact_id, mine.instance_id, "pizza")

    assert [h["snippet"] for h in hits] == ["pizza de calabresa"]


def test_search_history_requires_every_term_and_is_case_insensitive(
    db, conversation_factory, add_message
):
    conversation = conversation_factory("conv-search-terms")
    add_message(conversation, 1, "user", "Pizza Toscana")
    add_message(conversation, 2, "user", "pizza de queijo")

    hits = memory.search_history(db, conversation.contact_id, conversation.instance_id, "PIZZA toscana")

    assert [h["snippet"] for h in hits] == ["Pizza Toscana"]


def test_search_history_treats_like_wildcards_literally(db, conversation_factory, add_message):
    conversation = conversation_factory("conv-search-wild")
    add_message(conversation, 1, "user", "desconto de 10% hoje")
    add_message(conversation, 2, "user", "desconto de 100 reais")

    hits = memory.search_history(db, conversation.contact_id, conversation.instance_id, "10%")

    assert [h["snippet"] for h in hits] == ["desconto de 10% hoje"]


def test_search_history_limits_results_and_truncates_snippets(db, conversation_factory, add_message):
    conversation = conversation_factory("conv-search-limit")
    for n in range(1, 13):
        add_message(conversation, n, "user", f"pedido {n} " + "x" * 500)

    hits = memory.search_history(db, conversation.contact_id, conversation.instance_id, "pedido")

    assert len(hits) == 8  # limit padrão
    assert all(len(h["snippet"]) <= 300 for h in hits)
    assert hits[0]["snippet"].startswith("pedido 12 ")  # mais recente primeiro (match no início)
    assert len(memory.search_history(db, conversation.contact_id, conversation.instance_id, "pedido", limit=3)) == 3


def test_search_history_with_blank_query_returns_nothing(db, conversation_factory, add_message):
    conversation = conversation_factory("conv-search-blank")
    add_message(conversation, 1, "user", "oi")

    assert memory.search_history(db, conversation.contact_id, conversation.instance_id, "   ") == []


def test_search_history_snippet_is_centered_on_the_first_match(db, conversation_factory, add_message):
    conversation = conversation_factory("conv-search-center")
    add_message(conversation, 1, "user", "a" * 400 + " toscana " + "b" * 400)

    hits = memory.search_history(db, conversation.contact_id, conversation.instance_id, "toscana")

    snippet = hits[0]["snippet"]
    assert len(snippet) <= 300
    assert "toscana" in snippet  # content[:300] perderia o termo
    assert snippet.startswith("a") and snippet.endswith("b")  # janela em volta, não só o fim


@pytest.mark.asyncio
async def test_summary_batch_is_capped_at_the_100_oldest_pending_messages(
    db, conversation_factory, add_message
):
    conversation = conversation_factory("conv-sum-cap-batch")
    _fill(conversation, add_message, 170)  # 150 fora da janela de 20
    client = FakeClient(text="Lote 1.")

    await memory.maybe_refresh_summary(db, client, "modelo-x", conversation)

    prompt = client.requests[0].messages[0]["content"]
    assert "Cliente: msg 1" in prompt.splitlines()
    assert "msg 100" in prompt
    assert "msg 101" not in prompt  # 101 em diante fica para o próximo lote
    from app.models import ConversationMemorySummary

    row = db.get(ConversationMemorySummary, conversation.id)
    assert row.message_count == 100

    client.text = "Lote 2."
    await memory.maybe_refresh_summary(db, client, "modelo-x", conversation)

    # restam 50 pendentes fora da janela (>= 20): o resumo avança pelo mesmo critério
    second = client.requests[1].messages[0]["content"]
    assert "Lote 1." in second
    assert "msg 101" in second and "msg 150" in second
    assert "msg 151" not in second
    assert memory.build_context(db, conversation)[0] == "Lote 2."
    assert db.get(ConversationMemorySummary, conversation.id).message_count == 150


@pytest.mark.asyncio
async def test_summary_refresh_follows_the_window_it_is_given(db, conversation_factory, add_message):
    conversation = conversation_factory("conv-sum-window")
    _fill(conversation, add_message, 30)  # com janela 10, 20 ficam fora
    client = FakeClient()

    await memory.maybe_refresh_summary(db, client, "modelo-x", conversation, window=10)

    assert len(client.requests) == 1
    assert "msg 20" in client.requests[0].messages[0]["content"]
    assert "msg 21" not in client.requests[0].messages[0]["content"]
    _, history = memory.build_context(db, conversation, window=10)
    assert history[0]["content"] == "msg 21"
