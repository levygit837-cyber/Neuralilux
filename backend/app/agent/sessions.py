"""Session de atendimento (ADR 0007): uma Conversation se divide em Sessions por inatividade.

A Session começa na primeira Message depois de `Company.session_timeout_minutes` sem Messages. A Recent
Window mostra só a Session atual; Summary e History Search continuam alcançando as anteriores. Cada Pack é
avisado, se tiver o gancho opcional `on_session_start`, quando uma Session nova substitui outra, para tratar o
que ficou pendente (ex.: Order aberto).
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.agent.clock import as_utc
from app.agent.contracts import Pack
from app.models import Company, Conversation, Message
from app.models.company import DEFAULT_SESSION_TIMEOUT_MINUTES


def roll_session(
    db: Session, conversation: Conversation, company: Company, packs: Iterable[Pack], at: datetime
) -> bool:
    """Abre uma Session nova se a Message de `at` chegou depois do limite de inatividade.

    Chamar antes de gravar a Message e de atualizar `last_message_at`. Devolve True quando uma Session
    anterior expirou (os Packs foram avisados); a primeira Message de uma Conversation só marca o início.
    Não faz commit: entra na transação que grava a Message.
    """
    at = as_utc(at)
    last = conversation.last_message_at
    if last is None:
        conversation.session_started_at = at
        return False

    timeout = timedelta(minutes=company.session_timeout_minutes or DEFAULT_SESSION_TIMEOUT_MINUTES)
    if at - as_utc(last) <= timeout:
        return False

    conversation.session_started_at = at
    for pack in packs:
        # Gancho opcional: Pack sem pendência de Session não precisa declará-lo.
        on_session_start = getattr(pack, "on_session_start", None)
        if on_session_start is not None:
            on_session_start(db, conversation)
    return True


def previous_message_at(
    db: Session, conversation_id: str, turn_message_ids: Collection[str], deferred_ids: Collection[str] = ()
) -> datetime | None:
    """Quando foi a Message anterior às que dispararam o Turn, ou None se elas são toda a Conversation.

    `deferred_ids` são Messages já gravadas que ficam para o Turn seguinte e não contam como anteriores.
    """
    skipped = [*turn_message_ids, *deferred_ids]
    query = db.query(Message.timestamp).filter(Message.conversation_id == conversation_id)
    if skipped:
        query = query.filter(Message.id.notin_(skipped))
    row = query.order_by(Message.timestamp.desc(), Message.id.desc()).first()
    return row[0] if row else None
