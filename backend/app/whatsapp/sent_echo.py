"""Eco `fromMe` de uma Message que a API enviou e a Evolution não devolveu com id (resposta do Agent, aviso do sistema).

`sender.send_and_persist` grava toda saída da API, e as sem id ficam com `message_id` NULL. Quando o eco chega pelo
webhook, ele é reconhecido no banco (Instance + JID + texto + janela curta), então vale entre processos: quem enviou e
quem consome o eco podem ser réplicas diferentes do worker (#92). O eco nunca vira atividade de Attendant (não reinicia
o timeout do Handoff, #35) nem uma segunda Message.

Só a API deixa `message_id` NULL numa Message `from_me`: o que um Attendant digita no celular chega pelo webhook, com id.
Por isso a marca é o próprio `message_id IS NULL`, sem coluna de origem. A gravação e o envio rodam sob o mesmo lock por
JID (`conversation_lock.SAVE`), então o eco nunca é lido antes de a Message de saída estar gravada.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.agent.clock import utc_now
from app.models import Message

ECHO_WINDOW = timedelta(minutes=2)


def adopt_echo(db: Session, instance_id: str, remote_jid: str, content: str | None, message_id: str | None) -> bool:
    """True se o eco é de uma saída da API ainda sem id: grava o id nela e consome a marca (vale uma vez)."""
    wanted = (content or "").strip()
    if not wanted or not message_id:
        return False
    candidates = (
        db.query(Message)
        .filter(
            Message.instance_id == instance_id,
            Message.remote_jid == remote_jid,
            Message.is_from_me.is_(True),
            Message.message_id.is_(None),
            Message.timestamp >= utc_now() - ECHO_WINDOW,
        )
        .order_by(Message.timestamp)
        .all()
    )
    sent = next((m for m in candidates if (m.content or "").strip() == wanted), None)
    if sent is None:
        return False
    sent.message_id = message_id
    db.commit()
    return True
