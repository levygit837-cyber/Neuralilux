"""Apoio dos testes do consumer: payload de webhook, execução e leitura das Messages."""
from datetime import datetime, timezone

from app.models import Message
from app.whatsapp.consumer import WhatsAppMessageConsumer

JID = "5511999990001@s.whatsapp.net"


def _now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def upsert(*, text="Oi", remote_jid=JID, message_id="in-1", from_me=False, ts=None, message=None, key_extra=None, instance="evo-t7"):
    key = {"remoteJid": remote_jid, "fromMe": from_me, "id": message_id, **(key_extra or {})}
    return {
        "event": "messages.upsert",
        "data": {
            "instance": instance,
            "data": {
                "key": key,
                "message": message if message is not None else {"conversation": text},
                "pushName": "Contato",
                "messageTimestamp": ts if ts is not None else _now(),
            },
        },
    }


async def process(consumer: WhatsAppMessageConsumer, payload: dict) -> None:
    await consumer.process_webhook_event(payload)
    await consumer.drain()


def messages(db) -> list[Message]:
    db.expire_all()
    return db.query(Message).order_by(Message.created_at, Message.message_id).all()
