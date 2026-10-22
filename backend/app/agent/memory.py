"""Memória por Conversation: Recent Window, Summary e History Search (ADR 0003)."""

from __future__ import annotations

import logging

from sqlalchemy import func, literal_column, tuple_
from sqlalchemy.orm import Query, Session

from app.agent.contracts import ChatMessage, MessagesClient, MessagesRequest
from app.core.config import settings
from app.models import Conversation, ConversationMemorySummary, Message

logger = logging.getLogger(__name__)

SUMMARY_BATCH_MAX = 100  # Messages por Summary: o resumo avança em lotes e nunca estoura o contexto
SUMMARY_MAX_CHARS = 1200
SUMMARY_MAX_TOKENS = 600
SEARCH_SNIPPET_CHARS = 300

_SUMMARY_SYSTEM = (
    "Você mantém o resumo de uma conversa de atendimento por WhatsApp entre um Cliente e o Agent "
    f"de uma empresa. Escreva em português do Brasil, em no máximo {SUMMARY_MAX_CHARS} caracteres. "
    "Una o resumo anterior (se houver) às novas mensagens. Preserve fatos úteis para atender depois: "
    "pedidos, itens, endereços, preferências, combinados e pendências. Responda só com o resumo."
)


def _role(message: Message) -> str:
    return "user" if message.direction == "incoming" else "assistant"


def _text_messages(db: Session, conversation_id: str) -> Query:
    return db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.message_type == "text",
        Message.content.isnot(None),
        Message.content != "",
    )


def _session_messages(db: Session, conversation: Conversation) -> Query:
    """Messages de texto da Session atual; sem Session registrada, a Conversation inteira."""
    query = _text_messages(db, conversation.id)
    if conversation.session_started_at is not None:
        query = query.filter(Message.timestamp >= conversation.session_started_at)
    return query


def _newest_first(query: Query) -> Query:
    return query.order_by(Message.timestamp.desc(), Message.id.desc())


def _oldest_first(query: Query) -> Query:
    return query.order_by(Message.timestamp.asc(), Message.id.asc())


def build_context(
    db: Session, conversation: Conversation, window: int = settings.MEMORY_WINDOW
) -> tuple[str | None, list[ChatMessage]]:
    """Summary (se houver) e Recent Window da Conversation, prontos para o prompt.

    A janela são as últimas `window` Messages de texto da Session atual (ADR 0007), em ordem cronológica;
    o que veio antes da Session fica para o Summary e a History Search. Messages consecutivas do mesmo papel viram uma só e a primeira é sempre `user`.
    """
    recent = _newest_first(_session_messages(db, conversation)).limit(window).all()
    recent.reverse()

    history: list[ChatMessage] = []
    for message in recent:
        role = _role(message)
        if history and history[-1]["role"] == role:
            history[-1]["content"] = f"{history[-1]['content']}\n{message.content}"
        elif history or role == "user":
            history.append({"role": role, "content": message.content})

    row = db.get(ConversationMemorySummary, conversation.id)
    return (row.summary if row else None), history


async def maybe_refresh_summary(
    db: Session,
    client: MessagesClient,
    model: str,
    conversation: Conversation,
    window: int = settings.MEMORY_WINDOW,
) -> None:
    """Atualiza o Summary quando há `settings.SUMMARY_EVERY` Messages fora da janela ainda não resumidas.

    `window` tem de ser o mesmo usado em `build_context`; por isso ambos partem de `settings.MEMORY_WINDOW`.
    Cada chamada resume no máximo as `SUMMARY_BATCH_MAX` Messages pendentes mais antigas; o que sobra
    entra no próximo refresh.

    Chamar depois que a resposta já foi enviada (ex.: `asyncio.create_task`), para não atrasar o
    Contact. O chamador TEM de passar a sua própria `Session`, nunca a do Turn: esta função roda
    concorrente ao Turn, faz `commit`/`rollback` e uma `Session` não é segura entre tarefas.
    Qualquer falha só é logada: o próximo Turn tenta de novo.
    """
    try:
        await _refresh_summary(db, client, model, conversation, window)
    except Exception:
        db.rollback()
        logger.warning(
            "Falha ao atualizar o Summary da Conversation %s", conversation.id, exc_info=True
        )


async def _refresh_summary(
    db: Session, client: MessagesClient, model: str, conversation: Conversation, window: int
) -> None:
    outside = _text_messages(db, conversation.id)
    # A Message mais recente fora da janela: a primeira além de `window` na Session atual ou, se a
    # Session cabe na janela, a última de uma Session anterior.
    window_start = _newest_first(_session_messages(db, conversation)).offset(window).first()
    if window_start is None and conversation.session_started_at is not None:
        window_start = _newest_first(outside.filter(Message.timestamp < conversation.session_started_at)).first()
    if window_start is None:
        return
    # Tudo até `window_start` ainda pode ser resumido.
    outside = outside.filter(
        tuple_(Message.timestamp, Message.id) <= (window_start.timestamp, window_start.id)
    )

    previous = db.get(ConversationMemorySummary, conversation.id)
    if previous is not None:
        covered = db.get(Message, previous.covered_until_message_id)
        outside = outside.filter(
            tuple_(Message.timestamp, Message.id) > (covered.timestamp, covered.id)
        )

    pending = _oldest_first(outside).limit(SUMMARY_BATCH_MAX).all()
    if len(pending) < settings.SUMMARY_EVERY:
        return

    transcript = "\n".join(
        f"{'Cliente' if _role(m) == 'user' else 'Agent'}: {m.content}" for m in pending
    )
    prompt = (
        f"Resumo anterior:\n{previous.summary if previous else '(nenhum)'}\n\n"
        f"Novas mensagens:\n{transcript}"
    )
    response = await client.create(
        MessagesRequest(
            model=model,
            system=_SUMMARY_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=SUMMARY_MAX_TOKENS,
            effort="low",
        )
    )
    text = "".join(b["text"] for b in response.content if b["type"] == "text").strip()
    if not text:
        raise ValueError("o modelo devolveu um Summary vazio")
    text = text[:SUMMARY_MAX_CHARS]

    if previous is None:
        db.add(
            ConversationMemorySummary(
                conversation_id=conversation.id,
                summary=text,
                covered_until_message_id=pending[-1].id,
                message_count=len(pending),
            )
        )
    else:
        previous.summary = text
        previous.covered_until_message_id = pending[-1].id
        previous.message_count += len(pending)
    db.commit()


def _snippet(content: str, terms: list[str]) -> str:
    """Até `SEARCH_SNIPPET_CHARS` caracteres em volta da primeira ocorrência de qualquer termo."""
    lowered = content.lower()
    positions = [
        i
        for term in terms
        if not term.startswith("-") and term.lower() != "or"
        for i in [lowered.find(term.strip('"').lower())]
        if i >= 0
    ]
    if len(content) <= SEARCH_SNIPPET_CHARS or not positions:
        return content[:SEARCH_SNIPPET_CHARS]
    start = max(0, min(positions) - SEARCH_SNIPPET_CHARS // 2)
    start = min(start, len(content) - SEARCH_SNIPPET_CHARS)
    return content[start : start + SEARCH_SNIPPET_CHARS]


def search_history(
    db: Session,
    contact_id: str,
    instance_id: str,
    query: str,
    limit: int = settings.HISTORY_SEARCH_LIMIT,
) -> list[dict[str, str]]:
    """History Search: busca textual nas Messages de todas as Conversations de um Contact.

    O escopo é sempre o Contact dentro da Instance; Messages de outros Contacts nunca entram.
    Devolve `{"date", "role", "snippet"}`: no Postgres ordenado por relevância (`ts_rank`), no SQLite
    (testes) pelas mais recentes. Em ambos, empate por data decrescente.
    """
    terms = query.split()
    if not terms:
        return []

    base = (
        db.query(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            Conversation.contact_id == contact_id,
            Conversation.instance_id == instance_id,
            Message.message_type == "text",
            Message.content.isnot(None),
            Message.content != "",
        )
    )

    if db.get_bind().dialect.name == "postgresql":
        # A expressão tem de ser idêntica à do índice GIN (migração 0004) para ele ser usado.
        document = func.to_tsvector(
            literal_column("'portuguese'"), func.coalesce(Message.content, "")
        )
        ts_query = func.websearch_to_tsquery(literal_column("'portuguese'"), query)
        rows = (
            base.filter(document.op("@@")(ts_query))
            .order_by(func.ts_rank(document, ts_query).desc(), Message.timestamp.desc())
            .limit(limit)
            .all()
        )
    else:
        for term in terms:
            escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            base = base.filter(Message.content.ilike(f"%{escaped}%", escape="\\"))
        rows = _newest_first(base).limit(limit).all()

    return [
        {
            "date": m.timestamp.isoformat(),
            "role": _role(m),
            "snippet": _snippet(m.content, terms),
        }
        for m in rows
    ]
