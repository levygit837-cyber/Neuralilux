"""
WhatsApp Message Consumer Worker
Processa os eventos do webhook da Evolution vindos do RabbitMQ.

Concorrência: o worker roda um único event loop e entrega até `RABBITMQ_PREFETCH` mensagens em
paralelo. Dentro de uma Conversation a ordem é mantida por um `asyncio.Lock`; entre Conversations
o processamento é paralelo.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Dict, Optional

import structlog
from sqlalchemy.orm import Session

from app.agent import executor
from app.core.database import SessionLocal
from app.models.models import Agent, Contact, Conversation, Instance, Message
from app.services.evolution_api import evolution_api
from app.services.message_queue_service import message_queue_service
from app.services.realtime_event_bus import realtime_event_bus

logger = structlog.get_logger()

# Resposta fixa para mídia sem texto: o Agent não é chamado.
MEDIA_REPLY = "Por enquanto só consigo ler mensagens de texto. Pode me escrever o que você precisa?"

# Mensagens mais antigas que isto, em relação ao início do consumer, são histórico (backlog de uma
# queda ou reconexão): ficam gravadas, mas o Agent não responde.
STALE_AFTER = timedelta(minutes=5)

# Chaves de `message` que só embrulham outra mensagem.
_WRAPPERS = ("ephemeralMessage", "viewOnceMessage", "viewOnceMessageV2", "documentWithCaptionMessage")
_MEDIA = {
    "imageMessage": ("image", "[Imagem]"),
    "videoMessage": ("video", "[Vídeo]"),
    "audioMessage": ("audio", "[Áudio]"),
    "documentMessage": ("document", "[Documento]"),
    "stickerMessage": ("sticker", "[Sticker]"),
}


@dataclass(frozen=True)
class ParsedContent:
    message_type: str
    content: str  # o que é gravado e mostrado na UI
    text: str  # texto que o Contact escreveu (corpo ou legenda); vazio em mídia sem legenda
    is_media: bool = False


def parse_content(message_data: Dict[str, Any]) -> ParsedContent:
    """Extrai tipo, conteúdo e texto de um `message` da Evolution."""
    message_data = message_data or {}
    for _ in range(len(_WRAPPERS)):
        wrapper = next((key for key in _WRAPPERS if isinstance(message_data.get(key), dict)), None)
        if wrapper is None:
            break
        message_data = message_data[wrapper].get("message") or {}

    if "conversation" in message_data:
        text = message_data["conversation"] or ""
        return ParsedContent("text", text, text)
    if "extendedTextMessage" in message_data:
        text = message_data["extendedTextMessage"].get("text") or ""
        return ParsedContent("text", text, text)
    for key, (message_type, placeholder) in _MEDIA.items():
        if key in message_data:
            caption = (message_data[key] or {}).get("caption") or ""
            return ParsedContent(message_type, caption or placeholder, caption, is_media=True)
    return ParsedContent("unknown", "[Mensagem]", "")


def resolve_remote_jid(key: Dict[str, Any], payload: Dict[str, Any]) -> str:
    """JID do Contact. Um `@lid` é trocado pelo número real (`remoteJidAlt`/`senderPn`) quando vier."""
    remote_jid = key.get("remoteJid") or ""
    if remote_jid.endswith("@lid"):
        alternate = key.get("remoteJidAlt") or key.get("senderPn") or payload.get("senderPn")
        if alternate:
            return alternate if "@" in alternate else f"{alternate}@s.whatsapp.net"
    return remote_jid


def is_ignored_chat(remote_jid: str) -> bool:
    """Grupos e broadcast (inclui `status@broadcast`) nunca passam pelo Agent."""
    return remote_jid.endswith("@g.us") or remote_jid.endswith("@broadcast")


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
        self._running = False
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
                await self._update_message_status(db, data)
            elif event == "connection.update":
                await self._update_connection_status(db, data)
            elif event == "qrcode.updated":
                await self._publish_qr_code_update(data)
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

            instance = self._find_instance(db, instance_name)
            if instance is None:
                logger.warning("Message for unknown instance discarded", instance_name=instance_name)
                return

            payload = self._unwrap_event_payload(data)
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
        timestamp = self._parse_message_timestamp(payload.get("messageTimestamp"))
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
        self._touch_conversation(conversation, parsed.content, timestamp, unread=not from_me)
        db.commit()
        logger.info(
            "Message saved to database",
            message_id=message_id,
            conversation_id=conversation.id,
            instance_id=instance.id,
            from_me=from_me,
        )

        await self._publish_message(instance_name, remote_jid, contact, conversation, message_id, parsed.content, timestamp, from_me)

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

    @staticmethod
    def _touch_conversation(conversation: Conversation, content: str, timestamp: datetime, *, unread: bool) -> None:
        conversation.last_message_at = timestamp
        conversation.last_message_preview = content[:200] if content else None
        conversation.updated_at = datetime.now(timezone.utc)
        if unread:
            conversation.unread_count = (conversation.unread_count or 0) + 1

    async def _publish_message(
        self,
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
        await realtime_event_bus.publish(
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

    async def _update_message_status(self, db: Session, data: Dict[str, Any]) -> None:
        """Update message status in database"""
        try:
            message_payload = self._unwrap_event_payload(data)
            message_id = message_payload.get("key", {}).get("id")
            status = self._normalize_message_status(message_payload.get("status"))
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

    async def _update_connection_status(self, db: Session, data: Dict[str, Any]) -> None:
        """Update instance connection status"""
        try:
            instance_name = data.get("instance")
            message_payload = self._unwrap_event_payload(data)
            state = message_payload.get("state")

            if instance_name and state:
                instance = self._find_instance(db, instance_name)
                if instance is None:
                    logger.warning("Connection update for unknown instance discarded", instance_name=instance_name)
                    return
                instance.status = self._normalize_connection_status(state)
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

    async def _publish_qr_code_update(self, data: Dict[str, Any]) -> None:
        payload = self._unwrap_event_payload(data)
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

    def _unwrap_event_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        nested = data.get("data")
        if isinstance(nested, dict):
            return nested
        return data

    def _find_instance(self, db: Session, instance_name: str) -> Optional[Instance]:
        """A Instance cadastrada; nome desconhecido nunca cria registro."""
        return db.query(Instance).filter(
            Instance.evolution_instance_id == instance_name,
            Instance.is_active == True  # noqa: E712
        ).first()

    def _normalize_message_status(self, status: Any) -> str:
        mapping = {
            "PENDING": "pending",
            "pending": "pending",
            "SERVER_ACK": "sent",
            "sent": "sent",
            "DELIVERY_ACK": "delivered",
            "delivered": "delivered",
            "READ": "read",
            "read": "read",
        }
        return mapping.get(status, "sent")

    def _normalize_connection_status(self, state: str) -> str:
        mapping = {
            "open": "connected",
            "connected": "connected",
            "connecting": "connecting",
            "close": "disconnected",
            "closed": "disconnected",
            "disconnected": "disconnected",
        }
        return mapping.get(state, state)

    def _parse_message_timestamp(self, value: Any) -> datetime:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)

        if isinstance(value, str):
            try:
                numeric = float(value)
                return datetime.fromtimestamp(numeric, tz=timezone.utc)
            except ValueError:
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    pass

        return datetime.now(timezone.utc)

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
                    await self._send_and_persist(db, instance, conversation, contact, MEDIA_REPLY)
                return
            if not parsed.text.strip():
                log.info("Message without text, Agent not called", message_type=parsed.message_type)
                return

            result = await executor.handle_incoming(db, conversation, contact, instance, parsed.text)
            if not result.reply_text:
                log.info("Agent returned no response", steps=result.steps)
                return

            await self._send_and_persist(db, instance, conversation, contact, result.reply_text)
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

    async def _send_and_persist(
        self, db: Session, instance: Instance, conversation: Conversation, contact: Contact, text: str
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
            self._touch_conversation(conversation, text, timestamp, unread=False)
            db.commit()
        except Exception:
            # A resposta já saiu; falhar ao gravar não pode reenviar nem derrubar o Turn.
            db.rollback()
            logger.exception("Failed to persist the Agent reply", message_id=sent_id)
            return
        await self._publish_message(
            instance_name, conversation.remote_jid, contact, conversation, sent_id, text, timestamp, True
        )

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
        self._running = True
        self._started_at = datetime.now(timezone.utc)
        self.register_consumers()
        await self.mq.start_consuming()

    async def stop(self) -> None:
        """Para de consumir, espera as entregas em voo e os Summaries pendentes."""
        logger.info("Stopping WhatsApp message consumer")
        self._running = False
        await self.mq.stop_consuming()
        await self.drain()

    async def drain(self) -> None:
        """Espera as tasks de fundo (Summaries) que ainda estão em andamento."""
        while self._background:
            await asyncio.gather(*tuple(self._background), return_exceptions=True)


whatsapp_consumer = WhatsAppMessageConsumer()
