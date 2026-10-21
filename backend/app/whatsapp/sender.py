"""
Saída do Agent: envia a resposta pela Evolution, grava a Message `from_me` e avisa a UI ao vivo.
"""
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from app.models import Contact, Conversation, Instance, Message
from app.realtime.event_bus import realtime_event_bus
from app.whatsapp.evolution_client import evolution_api

logger = structlog.get_logger()


def touch_conversation(conversation: Conversation, content: str, timestamp: datetime, *, unread: bool) -> None:
    conversation.last_message_at = timestamp
    conversation.last_message_preview = content[:200] if content else None
    conversation.updated_at = datetime.now(timezone.utc)
    if unread:
        conversation.unread_count = (conversation.unread_count or 0) + 1


async def publish_message(
    instance_name: str,
    remote_jid: str,
    contact: Contact,
    conversation: Conversation,
    message_id: Optional[str],
    content: str,
    timestamp: datetime,
    from_me: bool,
) -> None:
    name = contact.name or contact.phone_number
    event = (
        {
            "type": "incoming_message",
            "instance_name": instance_name,
            "conversation_id": remote_jid,
            "payload": {
                "conversation": {
                    "id": remote_jid,
                    "name": name,
                    "lastMessage": content,
                    "timestamp": timestamp.isoformat(),
                    "unreadCount": conversation.unread_count or 0,
                    "isOnline": False,
                    "avatar": contact.profile_pic_url,
                },
                "message": {
                    "id": message_id,
                    "conversationId": remote_jid,
                    "content": content,
                    "timestamp": timestamp.isoformat(),
                    "isOutgoing": from_me,
                    "status": "sent",
                    "sender": None if from_me else {"name": name},
                },
            },
        }
    )
    try:
        await realtime_event_bus.publish(event)
    except Exception:
        # Realtime é só a UI ao vivo: uma falha no Redis não pode impedir o Agent nem a resposta.
        logger.exception("Failed to publish message to realtime", message_id=message_id)


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
