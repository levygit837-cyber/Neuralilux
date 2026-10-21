"""
Saída do Agent: envia a resposta pela Evolution, grava a Message `from_me` e avisa a UI ao vivo.
"""
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.models import Contact, Conversation, Instance, Message
from app.whatsapp.evolution_client import evolution_api
from app.whatsapp.status_events import publish_message, touch_conversation

logger = structlog.get_logger()


async def send_and_persist(
    db: Session, instance: Instance, conversation: Conversation, contact: Contact, text: str
) -> None:
    """Envia pela Evolution e grava a resposta como Message `from_me`, com o id devolvido.

    Assim o eco do webhook (mesmo id) é descartado pelo dedup, e a UI recebe a resposta aqui.
    """
    instance_name = instance.evolution_instance_id or instance.name
    response = await evolution_api.send_text_message(
        instance_name=instance_name,
        remote_jid=conversation.remote_jid,
        text=text,
    )
    sent_id = ((response or {}).get("key") or {}).get("id")
    if not sent_id:
        # Sem id não há como deduplicar o eco; deixa o eco gravar a Message.
        logger.warning("Evolution did not return a message id; reply will be stored from the webhook echo")
        return

    timestamp = datetime.now(timezone.utc)
    try:
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
                timestamp=timestamp,
            )
        )
        touch_conversation(conversation, text, timestamp, unread=False)
        db.commit()
    except Exception:
        # A resposta já saiu; falhar ao gravar não pode reenviar nem derrubar o Turn.
        db.rollback()
        logger.exception("Failed to persist the Agent reply", message_id=sent_id)
        return
    await publish_message(
        instance_name, conversation.remote_jid, contact, conversation, sent_id, text, timestamp, True
    )
