"""Entrega da resposta: avisa os Packs que a resposta de um Turn chegou ao Contact.

Um Pack que precisa saber se o Contact viu algo (ex.: uma confirmação que o Pack mostrou) declara o gancho opcional
`on_reply_delivered(db, conversation, turn_id, at)`. O consumer chama `reply_delivered` só depois de o envio
dar certo; Turn que falhou, sem resposta ou com a resposta descartada nunca passa por aqui.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.contracts import Pack
from app.agent.pack_hooks import run_reply_delivered
from app.models import Conversation


def notify_reply_delivered(
    db: Session, conversation: Conversation, packs: Iterable[Pack], turn_id: str | None, at: datetime
) -> None:
    if turn_id is None:
        return
    run_reply_delivered(packs, db, conversation, turn_id, at)
