"""
Eventos de status do webhook da Evolution: status da Message, conexão da Instance e QR code.
Cada um grava o que mudou e avisa a UI ao vivo pelo event bus.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog
from sqlalchemy.orm import Session

from app.models import Instance, Message
from app.realtime.event_bus import realtime_event_bus
from app.whatsapp.webhook_parser import (
    normalize_connection_status,
    normalize_message_status,
    unwrap_event_payload,
)

logger = structlog.get_logger()


def find_instance(db: Session, instance_name: str) -> Optional[Instance]:
    """A Instance cadastrada; nome desconhecido nunca cria registro."""
    return db.query(Instance).filter(
        Instance.evolution_instance_id == instance_name,
        Instance.is_active == True  # noqa: E712
    ).first()


async def update_message_status(db: Session, data: Dict[str, Any]) -> None:
    """Update message status in database"""
    try:
        message_payload = unwrap_event_payload(data)
        message_id = message_payload.get("key", {}).get("id")
        status = normalize_message_status(message_payload.get("status"))
        instance_name = data.get("instance")

        if message_id and status:
            message = db.query(Message).filter(Message.message_id == message_id).first()
            if message:
                message.status = status
                db.commit()
                logger.info("Message status updated", message_id=message_id, status=status)
                await realtime_event_bus.publish(
                    {
                        "type": "message_status",
                        "instance_name": instance_name,
                        "conversation_id": message.remote_jid,
                        "payload": {
                            "messageId": message_id,
                            "status": status,
                        },
                    }
                )
    except Exception as e:
        logger.error("Error updating message status", error=str(e))
        db.rollback()


async def update_connection_status(db: Session, data: Dict[str, Any]) -> None:
    """Update instance connection status"""
    try:
        instance_name = data.get("instance")
        message_payload = unwrap_event_payload(data)
        state = message_payload.get("state")

        if instance_name and state:
            instance = find_instance(db, instance_name)
            if instance is None:
                logger.warning("Connection update for unknown instance discarded", instance_name=instance_name)
                return
            instance.status = normalize_connection_status(state)
            instance.updated_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("Connection status updated", instance=instance_name, status=state)
            await realtime_event_bus.publish(
                {
                    "type": "connection_status",
                    "instance_name": instance_name,
                    "payload": {
                        "status": instance.status,
                        "evolutionState": state,
                    },
                }
            )
    except Exception as e:
        logger.error("Error updating connection status", error=str(e))
        db.rollback()


async def publish_qr_code_update(data: Dict[str, Any]) -> None:
    payload = unwrap_event_payload(data)
    qrcode = payload.get("qrcode") or payload.get("qr") or payload.get("base64")
    if not qrcode:
        return

    await realtime_event_bus.publish(
        {
            "type": "qr_code",
            "instance_name": data.get("instance"),
            "payload": {
                "qrcode": qrcode,
            },
        }
    )
