"""O que o consumer faz com o Handoff a cada Message gravada: atividade do Attendant e expiração por timeout."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Conversation, Instance
from app.services import handoff_service
from app.whatsapp.sender import claim_agent_echo


async def track_handoff(
    db: Session, instance: Instance, conversation: Conversation, remote_jid: str, content: str | None, from_me: bool
) -> None:
    if from_me:
        # Só um Attendant escrevendo pelo celular reinicia o timeout; o eco de uma resposta do Agent não.
        if not claim_agent_echo(instance.id, remote_jid, content):
            handoff_service.record_attendant_activity(db, conversation)
    else:
        # Rede de segurança do timeout: o sweeper do worker roda a cada minuto, esta checagem é exata.
        await handoff_service.expire_if_due(db, conversation, instance)
