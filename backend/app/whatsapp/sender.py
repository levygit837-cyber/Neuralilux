"""
Saída do Agent: envia a resposta pela Evolution, grava a Message `from_me` e avisa a UI ao vivo.
"""
import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.conversation_lock import SAVE, conversation_lock, jid_scope
from app.models import Contact, Conversation, Instance, Message
from app.whatsapp.evolution_client import evolution_api
from app.whatsapp.status_events import publish_message, touch_conversation

logger = structlog.get_logger()


def _persist_reply(
    db: Session,
    instance: Instance,
    conversation: Conversation,
    contact: Contact,
    sent_id: str | None,
    text: str,
    sent_by: str | None,
    timestamp: datetime,
) -> None:
    """Grava a Message `from_me` e confirma. Bloqueante: roda em thread. Recarrega Conversation e Contact depois do
    commit (que expira os atributos) para o `publish_message` não ir ao banco de dentro do event loop."""
    db.add(
        Message(
            instance_id=instance.id,
            conversation_id=conversation.id,
            remote_jid=conversation.remote_jid,
            message_id=sent_id,
            message_type="text",
            content=text,
            direction="outgoing",
            status="sent",
            is_from_me=True,
            sent_by=sent_by,
            timestamp=timestamp,
        )
    )
    touch_conversation(conversation, text, timestamp, unread=False)
    db.commit()
    db.refresh(conversation)
    db.refresh(contact)


async def send_and_persist(
    db: Session, instance: Instance, conversation: Conversation, contact: Contact, text: str, *, sent_by: str | None = None
) -> datetime:
    """Envia pela Evolution e grava a saída como Message `from_me`, com o id devolvido.

    Devolve quando a saída saiu. Falha no envio levanta; falha só ao gravar não desfaz o envio.

    Assim o eco do webhook (mesmo id) é descartado pelo dedup, e a UI recebe a saída aqui.

    Sem id da Evolution a Message é gravada com `message_id` NULL, para a resposta do Agent e para o aviso da API
    (`sent_by="system"`, não é o Agent nem um Attendant): o eco depois a reconhece no banco (`sent_echo.adopt_echo`),
    entre processos.

    O envio e a gravação rodam sob o lock `SAVE` do JID, o mesmo que o consumer toma para gravar uma Message do webhook:
    o eco (que pode chegar antes de o envio voltar) espera a Message de saída estar gravada, em qualquer réplica.
    """
    instance_name = instance.evolution_instance_id or instance.name
    scope = jid_scope(instance.id, conversation.remote_jid)
    async with conversation_lock(db.get_bind(), SAVE, scope, wait=settings.LOCK_SAVE_WAIT_SECONDS):
        response = await evolution_api.send_text_message(
            instance_name=instance_name,
            remote_jid=conversation.remote_jid,
            text=text,
        )
        sent_id = ((response or {}).get("key") or {}).get("id") or None
        if not sent_id:
            logger.warning("Evolution did not return a message id", sent_by=sent_by)

        timestamp = datetime.now(timezone.utc)
        try:
            # Em thread, e termina antes de publicar: quem lê a Message `from_me` como prova de envio (recuperação do
            # Turn) a encontra commitada antes de a UI receber o evento.
            await asyncio.to_thread(_persist_reply, db, instance, conversation, contact, sent_id, text, sent_by, timestamp)
        except Exception:
            # A saída já saiu; falhar ao gravar não pode reenviar nem derrubar o Turn.
            db.rollback()
            logger.exception("Failed to persist the outgoing message", message_id=sent_id)
            return timestamp
    await publish_message(conversation, contact, sent_id, text, timestamp, True)
    return timestamp
