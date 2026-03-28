"""
WhatsApp Message Consumer Worker
Handles async processing of WhatsApp messages via RabbitMQ
"""
import asyncio
import structlog
from typing import Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.services.message_queue_service import message_queue_service
from app.services.realtime_event_bus import realtime_event_bus
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import Instance, Contact, Conversation, Message

logger = structlog.get_logger()


class WhatsAppMessageConsumer:
    """Consumer for processing WhatsApp messages asynchronously"""
    
    def __init__(self):
        self.mq = message_queue_service
        self._running = False
    
    async def process_incoming_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming WhatsApp message"""
        try:
            data = message.get("data", {})
            logger.info(
                "Processing incoming WhatsApp message",
                message_id=data.get("message_id"),
                instance=data.get("instance")
            )
            
            # TODO: Implement full message processing pipeline
            # 1. Save message to database
            # 2. Check if instance has AI agent assigned
            # 3. If agent exists, send to AI processing queue
            # 4. Update conversation context
            
            logger.info("Incoming message processed", message_type=data.get("messageType"))
            
            return {
                "status": "processed",
                "message_id": data.get("message_id"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Error processing incoming message", error=str(e))
            raise
    
    async def process_outgoing_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process an outgoing message to be sent via WhatsApp"""
        try:
            data = message.get("data", {})
            logger.info(
                "Processing outgoing WhatsApp message",
                to=data.get("to"),
                instance=data.get("instance_name")
            )
            
            # TODO: Implement message sending via Evolution API
            # 1. Get instance connection details
            # 2. Call Evolution API to send message
            # 3. Update message status in database
            # 4. Publish status update to notifications queue
            
            logger.info("Outgoing message processed", recipient=data.get("to"))
            
            return {
                "status": "sent",
                "to": data.get("to"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Error processing outgoing message", error=str(e))
            raise
    
    async def process_ai_request(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process an AI agent request"""
        try:
            data = message.get("data", {})
            logger.info("Processing AI request", instance=data.get("instance"))
            
            # TODO: Implement AI processing
            # 1. Get agent configuration for instance
            # 2. Load conversation history
            # 3. If RAG enabled, search relevant documents
            # 4. Call AI model (OpenAI/Anthropic)
            # 5. Queue response for sending
            
            logger.info("AI request processed")
            
            return {
                "status": "processed",
                "has_response": False,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Error processing AI request", error=str(e))
            raise
    
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
        """Save incoming message to database"""
        try:
            instance_name = data.get("instance")
            if not instance_name:
                logger.warning("No instance name in message data")
                return

            instance = self._get_or_create_instance(db, instance_name)
            
            message_payload = self._unwrap_event_payload(data)
            message_data = message_payload.get("message", {}) or {}
            key = message_payload.get("key", {})
            remote_jid = key.get("remoteJid", "")
            message_id = key.get("id", "")
            from_me = key.get("fromMe", False)
            push_name = message_payload.get("pushName")
            timestamp = self._parse_message_timestamp(message_payload.get("messageTimestamp"))

            # Extract message content
            content = ""
            message_type = "text"
            if "conversation" in message_data:
                content = message_data["conversation"]
            elif "extendedTextMessage" in message_data:
                content = message_data["extendedTextMessage"].get("text", "")
            elif "imageMessage" in message_data:
                content = message_data["imageMessage"].get("caption", "[Imagem]")
                message_type = "image"
            elif "videoMessage" in message_data:
                content = message_data["videoMessage"].get("caption", "[Vídeo]")
                message_type = "video"
            elif "audioMessage" in message_data:
                content = "[Áudio]"
                message_type = "audio"
            elif "documentMessage" in message_data:
                content = message_data["documentMessage"].get("caption", "[Documento]")
                message_type = "document"
            else:
                content = "[Mensagem]"
                message_type = "unknown"
            
            # Extract a compact phone/group identifier from the WhatsApp JID.
            local_part = remote_jid.split("@")[0] if "@" in remote_jid else remote_jid
            phone_number = local_part.split("-")[0][:20]
            
            # Find or create contact
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
            else:
                contact.remote_jid = remote_jid
                if push_name:
                    contact.push_name = push_name
                    if not contact.name or contact.name == phone_number:
                        contact.name = push_name

            # Find or create conversation
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
            
            # Check if message already exists
            existing_message = db.query(Message).filter(
                Message.message_id == message_id
            ).first()
            
            if existing_message:
                logger.info("Message already exists", message_id=message_id)
                return

            # Save message
            db_message = Message(
                instance_id=instance.id,
                conversation_id=conversation.id,
                remote_jid=remote_jid,
                message_id=message_id,
                message_type=message_type,
                content=content,
                direction="incoming" if not from_me else "outgoing",
                status="sent",
                is_from_me=from_me,
                timestamp=timestamp
            )
            db.add(db_message)

            # Update conversation
            conversation.last_message_at = timestamp
            conversation.last_message_preview = content[:200] if content else None
            conversation.updated_at = datetime.now(timezone.utc)
            if not from_me:
                conversation.unread_count = (conversation.unread_count or 0) + 1

            db.commit()
            db.refresh(db_message)

            # === AGENTE AI: Processar mensagem com o agente se a instância tem agente atribuído ===
            if not from_me and content and message_type == "text":
                await self._try_process_with_agent(
                    db=db,
                    instance=instance,
                    conversation=conversation,
                    remote_jid=remote_jid,
                    contact_name=contact.name or phone_number,
                    content=content,
                )
            logger.info(
                "Message saved to database",
                message_id=message_id,
                conversation_id=conversation.id,
                instance_id=instance.id
            )

            await realtime_event_bus.publish(
                {
                    "type": "incoming_message",
                    "instance_name": instance_name,
                    "conversation_id": remote_jid,
                    "payload": {
                        "conversation": {
                            "id": remote_jid,
                            "name": contact.name or phone_number,
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
                            "sender": None if from_me else {"name": contact.name or phone_number},
                        },
                    },
                }
            )

        except Exception as e:
            logger.error("Error saving message to database", error=str(e))
            db.rollback()
            raise

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
                instance = self._get_or_create_instance(db, instance_name)
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

    def _get_or_create_instance(self, db: Session, instance_name: str) -> Instance:
        instance = db.query(Instance).filter(
            Instance.evolution_instance_id == instance_name,
            Instance.is_active == True
        ).first()
        if instance:
            return instance

        instance = Instance(
            name=instance_name,
            evolution_instance_id=instance_name,
            status="connected",
            is_active=True,
        )
        db.add(instance)
        db.flush()
        logger.info("Created placeholder instance for realtime event", instance_name=instance_name)
        return instance

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
        remote_jid: str,
        contact_name: str,
        content: str,
    ) -> None:
        """
        Tenta processar a mensagem com o agente AI se a instância tem um agente atribuído.
        """
        try:
            # Verificar se o agente está habilitado para esta instância
            if not instance.agent_enabled:
                logger.info("Agent disabled for this instance", instance_id=instance.id, instance_name=instance.name)
                return

            # Verificar se a instância tem um agente atribuído
            if not instance.agent_id:
                return

            # Verificar se o agente está ativo
            from app.models.models import Agent
            agent = db.query(Agent).filter(
                Agent.id == instance.agent_id,
                Agent.is_active == True
            ).first()

            if not agent:
                logger.info("Agent not found or inactive", agent_id=instance.agent_id)
                return

            logger.info(
                "Processing message with AI agent",
                agent_id=agent.id,
                agent_name=agent.name,
                conversation_id=str(conversation.id)
            )

            # Processar com o agente
            from app.agents.agent_executor import whatsapp_agent

            response = await whatsapp_agent.process_message(
                conversation_id=str(conversation.id),
                instance_id=str(instance.id),
                instance_name=instance.name or instance.evolution_instance_id or "",
                remote_jid=remote_jid,
                contact_name=contact_name,
                message=content,
            )

            if response:
                logger.info(
                    "Agent response sent",
                    conversation_id=str(conversation.id),
                    response_length=len(response)
                )
            else:
                logger.info("Agent returned no response", conversation_id=str(conversation.id))

        except Exception as e:
            logger.error(
                "Error processing message with agent",
                conversation_id=str(conversation.id),
                error=str(e)
            )
    
    def register_consumers(self):
        """Register all consumer callbacks"""
        self.mq.register_consumer("whatsapp.messages.incoming", self.process_incoming_message)
        self.mq.register_consumer("whatsapp.messages.send", self.process_outgoing_message)
        self.mq.register_consumer("ai.processing", self.process_ai_request)
        self.mq.register_consumer("webhooks.evolution", self.process_webhook_event)
        logger.info("All WhatsApp consumers registered")
    
    def start(self):
        """Start consuming messages"""
        logger.info("Starting WhatsApp message consumer")
        self._running = True
        self.register_consumers()
        self.mq.start_consuming()
    
    def stop(self):
        """Stop consuming messages"""
        logger.info("Stopping WhatsApp message consumer")
        self._running = False
        self.mq.stop_consuming()


whatsapp_consumer = WhatsAppMessageConsumer()
