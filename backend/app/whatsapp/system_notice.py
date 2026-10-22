"""Eco `fromMe` de um aviso da API (ex.: status do Order, #34) que a Evolution enviou sem devolver id.

`sender.send_and_persist(sent_by="system")` grava o aviso com `message_id` NULL. Quando o eco chega pelo webhook,
ele é reconhecido no banco (Conversation + texto + janela curta), então vale entre processos (API grava, worker
consome) e o eco nunca vira atividade de Attendant nem uma segunda Message.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.agent.clock import utc_now
from app.models import Message

ECHO_WINDOW = timedelta(minutes=2)


def adopt_echo(db: Session, instance_id: str, remote_jid: str, content: str | None, message_id: str | None) -> bool:
    """True se o eco é de um aviso do sistema ainda sem id: grava o id nele e consome a marca (vale uma vez)."""
    if not content or not message_id:
        return False
    notice = (
        db.query(Message)
        .filter(
            Message.instance_id == instance_id,
            Message.remote_jid == remote_jid,
            Message.sent_by == "system",
            Message.message_id.is_(None),
            Message.content == content,
            Message.timestamp >= utc_now() - ECHO_WINDOW,
        )
        .order_by(Message.timestamp)
        .first()
    )
    if notice is None:
        return False
    notice.message_id = message_id
    db.commit()
    return True
