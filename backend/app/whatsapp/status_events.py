"""
Efeitos de um evento da Evolution sobre o estado e a UI ao vivo: status da Message, conexão da
Instance, QR code e a Message recebida. Cada um grava o que mudou e avisa pelo event bus.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog
from sqlalchemy.orm import Session

from app.models import Contact, Conversation, Instance, Message
from app.realtime.events import (
    ConnectionStatusUpdate,
    ConversationUpdated,
    MessageStatusUpdate,
    NewMessage,
    QrCodeUpdate,
)
from app.realtime.publish import publish_event
from app.whatsapp.webhook_parser import (
    MESSAGE_STATUS_RANK,
    normalize_connection_status,
    normalize_message_status,
    unwrap_event_payload,
)

logger = structlog.get_logger()


def touch_conversation(conversation: Conversation, content: str, timestamp: datetime, *, unread: bool) -> None:
    conversation.last_message_at = timestamp
    conversation.last_message_preview = content[:200] if content else None
    conversation.updated_at = datetime.now(timezone.utc)
    if unread:
        conversation.unread_count = (conversation.unread_count or 0) + 1


async def publish_message(
    conversation: Conversation,
    contact: Contact,
    message_id: Optional[str],
    content: str,
    timestamp: datetime,
    from_me: bool,
    sender_name: Optional[str] = None,
) -> None:
    """Avisa a UI de uma Message nova (`conversation_updated` + `new_message`). Falha de realtime só loga."""
    name = contact.name or contact.phone_number
    try:
        await publish_event(
            ConversationUpdated(
                instance_id=conversation.instance_id,
                conversation_id=conversation.id,
                contact_name=name,
                last_message=content,
                timestamp=timestamp,
                unread_count=conversation.unread_count or 0,
                avatar=contact.profile_pic_url,
            )
        )
        await publish_event(
            NewMessage(
                instance_id=conversation.instance_id,
                conversation_id=conversation.id,
                message_id=message_id,
                content=content,
                timestamp=timestamp,
                is_outgoing=from_me,
                status="sent",
                sender_name=None if from_me else (sender_name or name),
            )
        )
    except Exception:
        # Realtime é só a UI ao vivo: uma falha na montagem do evento não pode impedir o Agent nem a resposta.
        logger.exception("Failed to publish message to realtime", message_id=message_id)


def find_instance(db: Session, instance_name: str) -> Optional[Instance]:
    """A Instance ativa pelo nome da Evolution (a chave do webhook); nome desconhecido nunca cria registro.

    Não é o lookup das rotas HTTP: `app.api.access.resolve_instance` resolve a referência do cliente.
    """
    return db.query(Instance).filter(
        Instance.evolution_instance_id == instance_name,
        Instance.is_active == True  # noqa: E712
    ).first()


async def update_message_status(db: Session, data: Dict[str, Any]) -> None:
    """Grava o status da Message e avisa a UI. A Evolution manda `messages.update` plano: o id é `keyId`."""
    try:
        message_payload = unwrap_event_payload(data)
        message_id = message_payload.get("keyId")
        status = normalize_message_status(message_payload.get("status"))

        if not message_id or not status:
            logger.debug("Message status update ignored", message_id=message_id, evolution_status=message_payload.get("status"))
            return
        message = db.query(Message).filter(Message.message_id == message_id).first()
        if message is None:
            # O ack pode chegar antes de o `messages.upsert` ser gravado; ele não é reenfileirado e se perde.
            # `@broadcast` (status, listas) nunca é gravado pelo upsert: descartar é o esperado, não um alerta.
            level = logger.debug if str(message_payload.get("remoteJid") or "").endswith("@broadcast") else logger.warning
            level("Message status update for unknown message discarded", message_id=message_id, status=status)
            return
        # A Evolution reenvia (e reordena) webhooks: o status só avança, nunca volta de `read` para `delivered`.
        if MESSAGE_STATUS_RANK.get(message.status, -1) >= MESSAGE_STATUS_RANK[status]:
            logger.debug("Stale message status ignored", message_id=message_id, current=message.status, received=status)
            return
        message.status = status
        db.commit()
        logger.info("Message status updated", message_id=message_id, status=status)
        if message.conversation_id:
            await publish_event(
                MessageStatusUpdate(
                    instance_id=message.instance_id,
                    conversation_id=message.conversation_id,
                    message_id=message_id,
                    status=status,
                )
            )
    except Exception:
        logger.exception("Error updating message status")
        db.rollback()


# Instante (`date_time` do envelope) do último `connection.update` aplicado por Instance. Só em memória do
# processo: sem coluna para persistir (exigiria migração), um reinício do worker zera o histórico.
_last_connection_event: dict[str, datetime] = {}


def _event_time(data: Dict[str, Any]) -> Optional[datetime]:
    """`date_time` do envelope da Evolution, fixado quando o evento nasce e igual em todo reenvio."""
    value = data.get("date_time")
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


async def update_connection_status(db: Session, data: Dict[str, Any]) -> bool:
    """Grava a conexão da Instance e devolve se aplicou o evento.

    Um `connection.update` mais antigo que o já aplicado (reenvio) é ignorado e devolve `False`, para o
    consumer não reagir (ex.: importar histórico) a um `open` velho.
    """
    try:
        instance_name = data.get("instance")
        message_payload = unwrap_event_payload(data)
        state = message_payload.get("state")

        if instance_name and state:
            instance = find_instance(db, instance_name)
            if instance is None:
                logger.warning("Connection update for unknown instance discarded", instance_name=instance_name)
                return False
            event_time = _event_time(data)
            last = _last_connection_event.get(instance_name)
            if event_time and last and event_time < last:
                logger.debug("Stale connection update ignored", instance=instance_name, state=state, event_time=event_time.isoformat())
                return False
            if event_time:
                _last_connection_event[instance_name] = event_time
            instance.status = normalize_connection_status(state)
            instance.updated_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("Connection status updated", instance=instance_name, status=state)
            await publish_event(
                ConnectionStatusUpdate(instance_id=instance.id, status=instance.status, evolution_state=state)
            )
            return True
    except Exception:
        logger.exception("Error updating connection status")
        db.rollback()
    return False


async def publish_qr_code_update(db: Session, data: Dict[str, Any]) -> None:
    payload = unwrap_event_payload(data)
    qrcode = payload.get("qrcode") or payload.get("qr") or payload.get("base64")
    if not qrcode:
        return
    instance = find_instance(db, data.get("instance") or "")
    if instance is None:
        logger.warning("QR code for unknown instance discarded", instance_name=data.get("instance"))
        return
    await publish_event(QrCodeUpdate(instance_id=instance.id, qrcode=qrcode))
