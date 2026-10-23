"""Memória por Conversation: Recent Window, Summary e History Search (ADR 0003)."""

from __future__ import annotations

import logging
from collections.abc import Collection

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


def _after(query: Query, message: Message) -> Query:
    return query.filter(tuple_(Message.timestamp, Message.id) > (message.timestamp, message.id))


def build_context(
    db: Session,
    conversation: Conversation,
    exclude_ids: Collection[str] = (),
) -> tuple[str | None, list[ChatMessage]]:
    """Summary (se houver) e Recent Window da Conversation, prontos para o prompt.

    A janela são as Messages de texto da Session atual (ADR 0007) que o Summary ainda não cobre, em ordem
    cronológica; o que veio antes da Session fica para o Summary e a History Search. Ela desliza em blocos:
    quem a encurta é o Summary (`maybe_refresh_summary`), de `settings.MEMORY_WINDOW_BLOCK` em
    `settings.MEMORY_WINDOW_BLOCK` Messages, então entre dois cortes o histórico só cresce no fim e o prefixo
    se repete de um Turn para o outro. Como a janela começa exatamente onde o Summary termina, nenhuma Message
    fica fora dos dois. Messages consecutivas do mesmo papel viram uma só e a primeira é sempre `user`.

    `exclude_ids` tira da janela as Messages que disparam o Turn (já gravadas); quem chama as põe de volta, juntas, no fim.
    """
    row = db.get(ConversationMemorySummary, conversation.id)
    query = _session_messages(db, conversation)
    if row is not None:
        query = _after(query, db.get(Message, row.covered_until_message_id))
    if exclude_ids:
        query = query.filter(Message.id.notin_(exclude_ids))

    history: list[ChatMessage] = []
    for message in _oldest_first(query).all():
        role = _role(message)
        if history and history[-1]["role"] == role:
            history[-1]["content"] = f"{history[-1]['content']}\n{message.content}"
        elif history or role == "user":
            history.append({"role": role, "content": message.content})

    return (row.summary if row else None), history


async def maybe_refresh_summary(
    db: Session,
    client: MessagesClient,
    model: str,
    conversation: Conversation,
) -> None:
    """Corta a Recent Window quando ela passa de `settings.MEMORY_WINDOW` e resume o que saiu.

    O corte tira da janela as Messages mais antigas em blocos de `settings.MEMORY_WINDOW_BLOCK`: o mínimo de
    blocos para a janela voltar a caber (e um pouco mais, se for preciso para ela começar em `user`). O
    Summary passa a cobrir exatamente essas Messages: `covered_until_message_id` é onde a janela começa em
    `build_context`, então cortar e resumir são a mesma gravação e nenhuma Message fica fora dos dois.

    Este refresh roda depois da resposta. Até ele gravar, a janela pode estar acima do limite (uma ou duas
    Messages no caso normal, mais se o refresh falhar). Isso só deixa a janela maior por um tempo, nunca
    perde Message. Um Turn que começa antes do refresh gravar vê a janela antiga, inteira.

    Sem corte, Messages de Sessions anteriores ainda não resumidas viram Summary quando chegam a
    `settings.SUMMARY_EVERY`; até lá só a History Search as alcança.

    Cada chamada resume no máximo as `SUMMARY_BATCH_MAX` Messages pendentes mais antigas; o que sobra
    entra no próximo refresh.

    Chamar depois que a resposta já foi enviada (ex.: `asyncio.create_task`), para não atrasar o
    Contact. O chamador TEM de passar a sua própria `Session`, nunca a do Turn: esta função roda
    concorrente ao Turn, faz `commit`/`rollback` e uma `Session` não é segura entre tarefas.
    Qualquer falha só é logada: o próximo Turn tenta de novo.
    """
    try:
        await _refresh_summary(db, client, model, conversation)
    except Exception:
        db.rollback()
        logger.warning(
            "Falha ao atualizar o Summary da Conversation %s", conversation.id, exc_info=True
        )


def _cut_size(window: list[Message]) -> int:
    """Quantas Messages mais antigas saem da janela: blocos inteiros, e a janela que sobra começa em `user`."""
    overflow = len(window) - settings.MEMORY_WINDOW
    if overflow <= 0:
        return 0
    block = settings.MEMORY_WINDOW_BLOCK
    cut = -(-overflow // block) * block
    while cut < len(window) and _role(window[cut]) != "user":
        cut += 1
    return cut if cut < len(window) else 0


def _starts_with_user(pending: list[Message], following: list[Message]) -> list[Message]:
    """Encurta um lote truncado para que a janela que sobra comece em `user` (senão `build_context` a descartaria)."""
    if not following or _role(following[0]) == "user":
        return pending
    while pending:
        if _role(pending.pop()) == "user":
            break
    return pending


async def _refresh_summary(
    db: Session, client: MessagesClient, model: str, conversation: Conversation
) -> None:
    previous = db.get(ConversationMemorySummary, conversation.id)
    covered = db.get(Message, previous.covered_until_message_id) if previous else None

    in_session = _session_messages(db, conversation)
    outside = _text_messages(db, conversation.id)
    if covered is not None:
        in_session = _after(in_session, covered)
        outside = _after(outside, covered)
    cut = _cut_size(_oldest_first(in_session).all())
    if cut:
        # Tudo até a última Message do bloco; Sessions anteriores ainda não resumidas vão junto.
        last = _oldest_first(in_session).offset(cut - 1).first()
        outside = outside.filter(tuple_(Message.timestamp, Message.id) <= (last.timestamp, last.id))
    elif conversation.session_started_at is not None:
        outside = outside.filter(Message.timestamp < conversation.session_started_at)
    else:
        return

    rows = _oldest_first(outside).limit(SUMMARY_BATCH_MAX + 1).all()
    pending, following = rows[:SUMMARY_BATCH_MAX], rows[SUMMARY_BATCH_MAX:]
    if cut:
        pending = _starts_with_user(pending, following)
    if not pending or (not cut and len(pending) < settings.SUMMARY_EVERY):
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
