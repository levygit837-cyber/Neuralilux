"""
WhatsApp Message Consumer Worker
Processa os eventos do webhook da Evolution vindos do RabbitMQ.

Concorrência: o worker roda um único event loop e entrega até `RABBITMQ_PREFETCH` mensagens em
paralelo. Dentro de uma Conversation a gravação é serializada por um `asyncio.Lock`; entre Conversations
o processamento é paralelo.

Resposta durável (#91): a entrega só grava a Message do Contact com `turn_state = pending` e volta, então o broker a
confirma logo. O Turn roda fora da entrega (`TurnRunner`: agrupamento das Messages picadas, concorrência limitada) e a
`Recovery` retoma o que ficou pendente. Estados e regras de posse: `turn_state.py`.
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Dict

import structlog
from sqlalchemy.orm import Session

from app.agent import executor
from app.core.config import settings
from app.core.database import SessionLocal
from app.agent.sessions import roll_session
from app.models import Company, Conversation, Instance, Message
from app.packs.registry import packs_for
from app.whatsapp import history_sync, system_notice, turn_state
from app.whatsapp.message_store import get_or_create_contact, get_or_create_conversation, new_message
from app.whatsapp.message_queue import message_queue_service
from app.whatsapp.handoff_tracking import track_handoff
from app.whatsapp.recovery import Recovery
from app.whatsapp.turn_batcher import Entry
from app.whatsapp.turn_runner import TurnRunner, Work
from app.whatsapp.status_events import (
    find_instance,
    publish_message,
    publish_qr_code_update,
    touch_conversation,
    update_connection_status,
    update_message_status,
)
from app.whatsapp.webhook_parser import (
    is_group_chat,
    is_ignored_chat,
    is_invisible_message,
    parse_content,
    parse_message_timestamp,
    resolve_remote_jid,
    unwrap_event_payload,
)

logger = structlog.get_logger()

# Eventos da Evolution que anunciam histórico novo: disparam a importação da Instance.
HISTORY_EVENTS = ("messages.set", "chats.set", "contacts.set", "chats.upsert")

# Mensagens mais antigas que isto, em relação ao início do consumer, são histórico (backlog de uma
# queda ou reconexão): ficam gravadas, mas o Agent não responde.
STALE_AFTER = timedelta(minutes=5)

# Tempo máximo que o shutdown espera os Summaries pendentes (dentro de `SHUTDOWN_TIMEOUT_SECONDS`) antes de cancelá-los.
DRAIN_TIMEOUT = 10.0


class WhatsAppMessageConsumer:
    """Consumer for processing WhatsApp messages asynchronously"""

    def __init__(self):
        self.mq = message_queue_service
        self._started_at = datetime.now(timezone.utc)
        self._locks: Dict[str, list] = {}  # chave da Conversation -> [Lock, quantos a usam]
        self._background: set[asyncio.Task] = set()
        self._summarizing: set[str] = set()
        self._syncing: set[str] = set()
        # `SessionLocal` é lida a cada uso (e não ligada aqui): os testes a trocam.
        self.runner = TurnRunner(lambda: SessionLocal(), self._spawn_summary)
        self.recovery = Recovery(self.runner, lambda: SessionLocal())
        self._recovering: asyncio.Task | None = None

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
                applied = await update_connection_status(db, data)  # `open` velho reenviado não importa histórico
                if applied and unwrap_event_payload(data).get("state") == "open":
                    self._spawn_history_sync(db, data)
            elif event == "qrcode.updated":
                await publish_qr_code_update(db, data)
            elif event in HISTORY_EVENTS:
                self._spawn_history_sync(db, data)
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
                logger.info("Broadcast message ignored", message_id=message_id, remote_jid=remote_jid)
                return
            if is_invisible_message(payload.get("message") or {}):
                logger.info("Invisible message type skipped", message_id=message_id, remote_jid=remote_jid)
                return

            async with self._serialized(f"{instance.id}:{remote_jid}"):
                await self._handle_message(db, instance, payload, key, remote_jid, from_me)

        except Exception as e:
            logger.error("Error saving message to database", error=str(e))
            db.rollback()
            raise

    async def _handle_message(
        self,
        db: Session,
        instance: Instance,
        payload: Dict[str, Any],
        key: Dict[str, Any],
        remote_jid: str,
        from_me: bool,
    ) -> None:
        """Grava a Message e, se for do Contact e couber resposta, entrega-a ao `TurnRunner`. Nunca espera o Turn."""
        message_id = key.get("id") or None
        push_name = payload.get("pushName")
        timestamp = parse_message_timestamp(payload.get("messageTimestamp"))
        parsed = parse_content(payload.get("message") or {})
        is_group = is_group_chat(remote_jid)

        # Dedup antes de qualquer escrita: inclui o eco do webhook para a resposta do próprio Agent.
        existing = db.query(Message).filter(Message.message_id == message_id).first() if message_id else None
        if existing is not None:
            logger.info("Message already exists", message_id=message_id, from_me=from_me)
            if existing.turn_state == turn_state.PENDING:
                # Entrega repetida de uma Message cujo Turn não terminou: quem a recebeu antes morreu antes de confirmar.
                self.recovery.resume_redelivered(db, existing)
            return

        # Eco de um aviso da API enviado sem id (#34): já está gravado; não é Attendant nem Message nova.
        if from_me and system_notice.adopt_echo(db, instance.id, remote_jid, parsed.content, message_id):
            logger.info("Echo of a system notice matched", message_id=message_id)
            return

        # O pushName de uma mensagem `fromMe` é o do nosso número; o de uma mensagem de grupo é o do
        # participante. Nenhum dos dois é o nome do Contact.
        contact = get_or_create_contact(db, instance, remote_jid, push_name=None if from_me or is_group else push_name)
        conversation, _ = get_or_create_conversation(db, instance, contact, remote_jid)
        sender_name = push_name if is_group and not from_me else None

        if not from_me and not is_group:
            self._roll_session(db, instance, conversation, timestamp)

        skip = turn_state.skip_reason(from_me, remote_jid, timestamp, self._started_at - STALE_AFTER)
        claimed_at = turn_state.now()  # a Message pendente já nasce com dono: este processo
        stored = new_message(
            instance, conversation, remote_jid, message_id, parsed, from_me, timestamp, sender_name=sender_name,
            turn=turn_state.initial_state(skip, claimed_at),
        )
        stored_id = stored.id  # lido antes do commit: depois dele o objeto expira e `.id` custaria uma consulta
        db.add(stored)
        touch_conversation(conversation, parsed.content, timestamp, unread=not from_me)
        db.commit()
        # Sem `await` entre o commit e o `hold`: a líder do agrupamento não fecha o grupo com esta Message a caminho.
        hold = None if skip else self.runner.batcher.hold(str(conversation.id))
        logger.info(
            "Message saved to database",
            message_id=message_id,
            conversation_id=conversation.id,
            instance_id=instance.id,
            from_me=from_me,
        )

        try:
            if from_me and not is_group:  # o Contact já foi respondido (Attendant ou eco da resposta): fecha as pendentes
                turn_state.answer_started(db, conversation.id, claimed_at, self.runner.running_ids)
            await publish_message(
                conversation, contact, message_id, parsed.content, timestamp, from_me, sender_name
            )

            if not is_group:  # Session e Handoff são do atendimento 1:1
                await track_handoff(db, instance, conversation, remote_jid, parsed.content, from_me)

            if skip:
                logger.info("Message not processed by agent", message_id=message_id, reason=skip)
                return
            db.rollback()  # a líder espera a pausa do Contact: não segura a conexão do pool enquanto isso
            work = Work(instance.id, conversation.id, contact.id, Entry(stored_id, parsed.text, timestamp, claimed_at), parsed)
            self.runner.spawn([work], hold)
        except BaseException:
            if hold is not None:
                hold.release()
            raise

    @staticmethod
    def _roll_session(db: Session, instance: Instance, conversation: Conversation, timestamp: datetime) -> None:
        """Message do Contact depois do limite de inatividade da Company abre uma Session nova (ADR 0007).

        Entra na transação que grava a Message: Session nova e Order abandonado saem juntos ou nenhum.
        Contact novo numa Instance sem Company também ganha Session; só não há Pack para avisar.
        """
        company = db.get(Company, instance.company_id) if instance.company_id else None
        if company is None:
            return
        roll_session(db, conversation, company, packs_for(company), timestamp)

    def _spawn_history_sync(self, db: Session, data: Dict[str, Any]) -> None:
        """Importa o histórico da Instance numa task rastreada; no máximo uma por Instance."""
        instance = find_instance(db, data.get("instance") or "")
        if instance is None or instance.id in self._syncing:
            return
        self._syncing.add(instance.id)
        task = asyncio.create_task(self._run_history_sync(instance.id))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _run_history_sync(self, instance_id: str) -> None:
        sync_db = SessionLocal()
        try:
            instance = sync_db.get(Instance, instance_id)
            if instance is not None:
                await history_sync.sync_instance(sync_db, instance)
        except history_sync.SyncAlreadyRunning:
            logger.info("History sync skipped: another process is already importing", instance_id=instance_id)
        except Exception:
            logger.exception("History sync failed", instance_id=instance_id)
        finally:
            sync_db.close()
            self._syncing.discard(instance_id)

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
        """Consome até `stop()`. A recuperação varre as Messages pendentes na subida e depois periodicamente."""
        logger.info("Starting WhatsApp message consumer")
        self._started_at = datetime.now(timezone.utc)
        self.register_consumers()
        self._recovering = asyncio.create_task(self.recovery.run_forever())
        await self.mq.start_consuming()

    async def stop(self) -> None:
        """Para de consumir e espera os Turns em voo até `SHUTDOWN_TIMEOUT_SECONDS`; o que sobrar é cancelado e fica pendente
        (a recuperação retoma). Depois espera os Summaries e as importações de histórico dentro do que resta do prazo."""
        logger.info("Stopping WhatsApp message consumer")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + settings.SHUTDOWN_TIMEOUT_SECONDS
        if self._recovering is not None:
            self._recovering.cancel()
            await asyncio.gather(self._recovering, return_exceptions=True)
            self._recovering = None
        await self.mq.stop_consuming()
        await self.runner.shutdown(max(0.0, deadline - loop.time()))
        pending = tuple(self._background)
        if pending:
            timeout = min(DRAIN_TIMEOUT, max(0.0, deadline - loop.time()))
            _, unfinished = await asyncio.wait(pending, timeout=timeout)
            for task in unfinished:
                task.cancel()
            if unfinished:
                logger.error(
                    "Background tasks cancelled (summaries/history syncs): shutdown drain timed out",
                    pending=len(unfinished),
                    timeout=timeout,
                )
                await asyncio.gather(*unfinished, return_exceptions=True)

    async def drain(self) -> None:
        """Espera os Turns e as tasks de fundo (Summaries e importações de histórico) que ainda estão em andamento."""
        while pending := {task for task in (*self.runner.tasks, *self._background) if not task.done()}:
            await asyncio.wait(pending)


whatsapp_consumer = WhatsAppMessageConsumer()
