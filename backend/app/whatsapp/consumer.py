"""
WhatsApp Message Consumer Worker
Processa os eventos do webhook da Evolution vindos do RabbitMQ.

Concorrência: o worker roda um único event loop e entrega até `RABBITMQ_PREFETCH` mensagens em
paralelo. Dentro de uma Conversation a ordem é mantida por um `asyncio.Lock`; entre Conversations
o processamento é paralelo.
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Dict, Optional

import structlog
from sqlalchemy.orm import Session

from app.agent import executor
from app.core.database import SessionLocal
from app.models import Agent, Contact, Conversation, Instance, Message
from app.whatsapp.message_queue import message_queue_service
from app.whatsapp.sender import send_and_persist
from app.whatsapp.status_events import (
    find_instance,
    publish_message,
    publish_qr_code_update,
    touch_conversation,
    update_connection_status,
    update_message_status,
)
from app.whatsapp.webhook_parser import (
    ParsedContent,
    is_ignored_chat,
    parse_content,
    parse_message_timestamp,
    resolve_remote_jid,
    unwrap_event_payload,
)

logger = structlog.get_logger()

# Resposta fixa para mídia sem texto: o Agent não é chamado.
MEDIA_REPLY = "Por enquanto só consigo ler mensagens de texto. Pode me escrever o que você precisa?"

# Mensagens mais antigas que isto, em relação ao início do consumer, são histórico (backlog de uma
# queda ou reconexão): ficam gravadas, mas o Agent não responde.
STALE_AFTER = timedelta(minutes=5)

# Tempo máximo que o shutdown espera os Summaries pendentes antes de cancelá-los.
DRAIN_TIMEOUT = 10.0


def _resolve_default_agent(db: Session, instance: Instance) -> Agent | None:
    """O Agent da Instance: o ligado a ela e, na falta, o Agent ativo da Company."""
    if instance.agent_id:
        agent = db.query(Agent).filter(Agent.id == instance.agent_id, Agent.is_active == True).first()  # noqa: E712
        if agent:
            return agent
    if instance.company_id:
        agent = (
            db.query(Agent)
            .filter(Agent.company_id == instance.company_id, Agent.is_active == True)  # noqa: E712
            .order_by(Agent.created_at, Agent.id)
            .first()
        )
        if agent:
            instance.agent_id = agent.id
            db.commit()
            return agent
    return None


class WhatsAppMessageConsumer:
    """Consumer for processing WhatsApp messages asynchronously"""

    def __init__(self):
        self.mq = message_queue_service
        self._started_at = datetime.now(timezone.utc)
        self._locks: Dict[str, list] = {}  # chave da Conversation -> [Lock, quantos a usam]
        self._background: set[asyncio.Task] = set()
        self._summarizing: set[str] = set()
        self._missing_agent_logged: set[str] = set()

    @asynccontextmanager
    async def _serialized(self, key: str) -> AsyncIterator[None]:
        """Uma Conversation por vez; Conversations diferentes em paralelo. O Lock some quando ninguém o usa."""
        entry = self._locks.get(key)
        if entry is None:
            entry = self._locks[key] = [asyncio.Lock(), 0]
        entry[1] += 1
        try:
            async with entry[0]:
                yield
        finally:
            entry[1] -= 1
            if entry[1] == 0:
                del self._locks[key]

    async def process_webhook_event(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process an Evolution API webhook event"""
        db: Session = SessionLocal()
        try:
            event = message.get("event") or message.get("data", {}).get("event")
            data = message.get("data", {})
            
            logger.info(
                "Processing webhook event",
                webhook_event=event,
                instance=data.get("instance"),
            )
            
            if event == "messages.upsert":
                await self._save_message_to_database(db, data)
            elif event == "messages.update":
                await update_message_status(db, data)
            elif event == "connection.update":
                await update_connection_status(db, data)
            elif event == "qrcode.updated":
                await publish_qr_code_update(data)
            else:
                logger.warning("Unknown webhook event", webhook_event=event)
            
            return {
                "status": "processed",
                "event": event,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error("Error processing webhook event", error=str(e))
            db.rollback()
            raise
        finally:
            db.close()

    async def _save_message_to_database(self, db: Session, data: Dict[str, Any]) -> None:
        """Grava a Message recebida e, se couber, deixa o Agent responder."""
        try:
            instance_name = data.get("instance")
            if not instance_name:
                logger.warning("No instance name in message data")
                return

            instance = find_instance(db, instance_name)
            if instance is None:
                logger.warning("Message for unknown instance discarded", instance_name=instance_name)
                return

            payload = unwrap_event_payload(data)
            key = payload.get("key") or {}
            remote_jid = resolve_remote_jid(key, payload)
            message_id = key.get("id") or None
            from_me = bool(key.get("fromMe", False))

            if is_ignored_chat(remote_jid):
                logger.info("Group or broadcast message ignored", message_id=message_id, remote_jid=remote_jid)
                return

            async with self._serialized(f"{instance.id}:{remote_jid}"):
                await self._handle_message(db, instance, instance_name, payload, key, remote_jid, from_me)

        except Exception as e:
            logger.error("Error saving message to database", error=str(e))
            db.rollback()
            raise

    async def _handle_message(
        self,
        db: Session,
        instance: Instance,
        instance_name: str,
        payload: Dict[str, Any],
        key: Dict[str, Any],
        remote_jid: str,
        from_me: bool,
    ) -> None:
        message_id = key.get("id") or None
        push_name = payload.get("pushName")
        timestamp = parse_message_timestamp(payload.get("messageTimestamp"))
        parsed = parse_content(payload.get("message") or {})

        # Dedup antes de qualquer escrita: inclui o eco do webhook para a resposta do próprio Agent.
        if message_id and db.query(Message.id).filter(Message.message_id == message_id).first():
            logger.info("Message already exists", message_id=message_id, from_me=from_me)
            return

        local_part = remote_jid.split("@")[0] if "@" in remote_jid else remote_jid
        phone_number = local_part.split("-")[0][:20]

        contact = db.query(Contact).filter(
            Contact.instance_id == instance.id,
            Contact.remote_jid == remote_jid
        ).first()
        if not contact:
            contact = Contact(
                instance_id=instance.id,
                phone_number=phone_number,
                remote_jid=remote_jid,
                name=push_name or phone_number,
                push_name=push_name,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.add(contact)
            db.flush()
        elif push_name and not from_me:
            # Em mensagem `fromMe` o pushName é o do nosso próprio número, não o do Contact.
            contact.push_name = push_name
            if not contact.name or contact.name == phone_number:
                contact.name = push_name

        conversation = db.query(Conversation).filter(
            Conversation.instance_id == instance.id,
            Conversation.contact_id == contact.id
        ).first()
        if not conversation:
            conversation = Conversation(
                instance_id=instance.id,
                contact_id=contact.id,
                remote_jid=remote_jid,
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.add(conversation)
            db.flush()

        db.add(
            Message(
                instance_id=instance.id,
                conversation_id=conversation.id,
                remote_jid=remote_jid,
                message_id=message_id,
                message_type=parsed.message_type,
                content=parsed.content,
                direction="outgoing" if from_me else "incoming",
                status="sent",
                is_from_me=from_me,
                timestamp=timestamp,
            )
        )
        touch_conversation(conversation, parsed.content, timestamp, unread=not from_me)
        db.commit()
        logger.info(
            "Message saved to database",
            message_id=message_id,
            conversation_id=conversation.id,
            instance_id=instance.id,
            from_me=from_me,
        )

        await publish_message(instance_name, remote_jid, contact, conversation, message_id, parsed.content, timestamp, from_me)

        skip = self._skip_agent_reason(from_me, remote_jid, timestamp)
        if skip:
            logger.info("Message not processed by agent", message_id=message_id, reason=skip)
            return
        await self._try_process_with_agent(db, instance, conversation, contact, parsed)

    def _skip_agent_reason(self, from_me: bool, remote_jid: str, timestamp: datetime) -> Optional[str]:
        if from_me:
            return "from_me"
        if remote_jid.endswith("@lid"):
            return "unresolved_lid"  # sem o número real não há como responder
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        if timestamp < self._started_at - STALE_AFTER:
            return "stale"
        return None

    async def _try_process_with_agent(
        self,
        db: Session,
        instance: Instance,
        conversation: Conversation,
        contact: Contact,
        parsed: ParsedContent,
    ) -> None:
        """Roda um Turn do Agent para a Message recebida e envia a resposta, se houver."""
        log = logger.bind(instance_id=instance.id, conversation_id=str(conversation.id))
        try:
            if not instance.agent_enabled:
                log.info("Agent disabled for this instance")
                return

            agent = _resolve_default_agent(db, instance)
            if agent is None:
                # Um erro por Instance até o worker reiniciar: sem Agent, toda mensagem cairia aqui.
                if instance.id not in self._missing_agent_logged:
                    self._missing_agent_logged.add(instance.id)
                    log.error(
                        "No active Agent for this Instance or its Company; messages are not answered. "
                        "Run scripts/seed_data.py or create the Company's Agent",
                        company_id=instance.company_id,
                    )
                return
            self._missing_agent_logged.discard(instance.id)

            if parsed.is_media and not parsed.text.strip():
                if not self._in_handoff(db, conversation.id):
                    await send_and_persist(db, instance, conversation, contact, MEDIA_REPLY)
                return
            if not parsed.text.strip():
                log.info("Message without text, Agent not called", message_type=parsed.message_type)
                return

            result = await executor.handle_incoming(db, conversation, contact, instance, parsed.text)
            if not result.reply_text:
                log.info("Agent returned no response", steps=result.steps)
                return

            await send_and_persist(db, instance, conversation, contact, result.reply_text)
            log.info("Agent response sent", steps=result.steps, response_length=len(result.reply_text))
        except Exception:
            # Nunca derruba o worker: o erro fica no log e a próxima Message tenta de novo.
            log.exception("Unexpected error processing message with agent")
            return

        self._spawn_summary(conversation.id)

    @staticmethod
    def _in_handoff(db: Session, conversation_id: str) -> bool:
        flag = db.query(Conversation.human_in_loop).filter(Conversation.id == conversation_id).scalar()
        return bool(flag)

    def _spawn_summary(self, conversation_id: str) -> None:
        """Atualiza o Summary fora do caminho da resposta, numa task rastreada do loop do worker."""
        if conversation_id in self._summarizing:
            return
        self._summarizing.add(conversation_id)
        task = asyncio.create_task(self._refresh_summary(conversation_id))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _refresh_summary(self, conversation_id: str) -> None:
        try:
            await executor.refresh_summary(conversation_id)
        except Exception:
            logger.exception("Summary refresh failed after reply", conversation_id=conversation_id)
        finally:
            self._summarizing.discard(conversation_id)

    def register_consumers(self):
        """Register all consumer callbacks"""
        self.mq.register_consumer("webhooks.evolution", self.process_webhook_event)
        logger.info("All WhatsApp consumers registered")

    async def start(self) -> None:
        """Consome até `stop()`."""
        logger.info("Starting WhatsApp message consumer")
        self._started_at = datetime.now(timezone.utc)
        self.register_consumers()
        await self.mq.start_consuming()

    async def stop(self) -> None:
        """Para de consumir, espera as entregas em voo e os Summaries pendentes."""
        logger.info("Stopping WhatsApp message consumer")
        await self.mq.stop_consuming()
        pending = tuple(self._background)
        if pending:
            _, unfinished = await asyncio.wait(pending, timeout=DRAIN_TIMEOUT)
            for task in unfinished:
                task.cancel()
            if unfinished:
                logger.error(
                    "Summaries cancelled: shutdown drain timed out", pending=len(unfinished), timeout=DRAIN_TIMEOUT
                )
                await asyncio.gather(*unfinished, return_exceptions=True)

    async def drain(self) -> None:
        """Espera as tasks de fundo (Summaries) que ainda estão em andamento."""
        while self._background:
            await asyncio.gather(*tuple(self._background), return_exceptions=True)


whatsapp_consumer = WhatsAppMessageConsumer()
