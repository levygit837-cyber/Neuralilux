"""Socket.IO usado pelo frontend para receber eventos ao vivo.

As salas são por UUID: `instance:{id}` (lista, conexão, Handoff) e `conversation:{id}` (Thinking e Tools da Conversation
aberta). Quem entra numa sala passa antes pelo controle de acesso das rotas HTTP (`app.api.access.can_access_instance`);
nome da Instance ou `remote_jid` vindos do cliente nunca resolvem nada. Os eventos têm schema em `app.realtime.events`.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import socketio
import structlog
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.access import can_access_instance
from app.core.auth_cookie import auth_cookie_from_header
from app.core.config import settings
from app.core.conversation_lock import LockBusy
from app.core.database import SessionLocal
from app.models import Conversation, Instance, User
from app.realtime.events import EVENTS, conversation_room, instance_room
from app.services.user_service import get_active_user_from_token
from app.whatsapp.panel_send import send_from_panel
from app.whatsapp.sender import Recipient

logger = structlog.get_logger()


class ChatSocketService:
    def __init__(self) -> None:
        self.server = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins=settings.CORS_ORIGINS,
            logger=False,
            engineio_logger=False,
        )
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.server.event
        async def connect(
            sid: str,
            environ: dict[str, Any],
            auth: Optional[dict[str, Any]] = None,
        ):
            # Navegador: cookie httpOnly no handshake. `auth.token` segue valendo para clientes que não são navegador.
            token = (auth or {}).get("token") or auth_cookie_from_header(environ.get("HTTP_COOKIE"))
            user = await asyncio.to_thread(self._get_user_from_token, token) if token else None

            if not user:
                logger.warning("Frontend socket authentication failed", sid=sid)
                # Recusa com motivo: o cliente distingue sessão inválida (encerra) de backend fora do ar (tenta de novo).
                raise socketio.exceptions.ConnectionRefusedError("unauthorized")

            await self.server.save_session(sid, {"user_id": user.id, "email": user.email})
            logger.info("Frontend socket connected", sid=sid, user_id=user.id)

        @self.server.event
        async def disconnect(sid: str):
            logger.info("Frontend socket disconnected", sid=sid)

        @self.server.on("subscribe_instance")
        async def subscribe_instance(sid: str, data: Any):
            user_id = await self._user_id(sid)
            instance_id = _ref(data, "instanceId")
            if not instance_id or not user_id:
                return {"ok": False}
            if not await asyncio.to_thread(self._user_can_access_instance, user_id, instance_id):
                return {"ok": False}

            await self.server.enter_room(sid, instance_room(instance_id))
            logger.info("Frontend socket subscribed to instance", sid=sid, instance_id=instance_id, user_id=user_id)
            return {"ok": True}

        @self.server.on("leave_instance")
        async def leave_instance(sid: str, data: Any):
            instance_id = _ref(data, "instanceId")
            if not instance_id:
                return {"ok": False}
            await self.server.leave_room(sid, instance_room(instance_id))
            return {"ok": True}

        @self.server.on("join_conversation")
        async def join_conversation(sid: str, data: Any):
            user_id = await self._user_id(sid)
            instance_id, conversation_id = _ref(data, "instanceId"), _ref(data, "conversationId")
            if not instance_id or not conversation_id or not user_id:
                return {"ok": False}
            # A Conversation tem de ser da Instance que o usuário acessa: nenhuma outra sala dela se abre.
            target = await asyncio.to_thread(self._authorized_conversation, user_id, instance_id, conversation_id)
            if target is None:
                logger.warning("Realtime join_conversation denied", sid=sid, user_id=user_id, instance_id=instance_id)
                return {"ok": False}

            await self.server.enter_room(sid, conversation_room(conversation_id))
            return {"ok": True}

        @self.server.on("leave_conversation")
        async def leave_conversation(sid: str, data: Any):
            conversation_id = _ref(data, "conversationId")
            if not conversation_id:
                return {"ok": False}
            await self.server.leave_room(sid, conversation_room(conversation_id))
            return {"ok": True}

        @self.server.on("send_message")
        async def send_message(sid: str, data: Any):
            user_id = await self._user_id(sid)
            instance_id, conversation_id = _ref(data, "instanceId"), _ref(data, "conversationId")
            content = data.get("content") if isinstance(data, dict) else None

            if not instance_id or not conversation_id or not content or not user_id:
                return {"ok": False}

            # Autoriza antes de falar com a Evolution. O JID de destino vem da Conversation, não do cliente.
            target = await asyncio.to_thread(self._authorized_conversation, user_id, instance_id, conversation_id)
            if target is None:
                logger.warning("Realtime send_message denied", sid=sid, user_id=user_id, instance_id=instance_id)
                return {"ok": False}

            # Mesmo caminho do worker e da rota HTTP (`send_and_persist`): lock SAVE, gravação em thread e eco do webhook.
            db = SessionLocal()
            try:
                sent = await send_from_panel(db, target, content)
            except LockBusy:
                logger.warning("Conversation busy, socket message not sent", instance_id=instance_id, conversation_id=conversation_id)
                return {"ok": False}
            except Exception:
                logger.exception("Socket send_message failed", instance_id=instance_id, conversation_id=conversation_id)
                return {"ok": False}
            finally:
                await asyncio.to_thread(db.close)
            return {"ok": True, "messageId": sent.message_id}

    async def _user_id(self, sid: str) -> Optional[str]:
        session = await self.server.get_session(sid)
        return session.get("user_id")

    def _get_user_from_token(self, token: Optional[str]) -> Optional[User]:
        if not token:
            return None

        db = SessionLocal()
        try:
            return get_active_user_from_token(db, token)
        finally:
            db.close()

    def _accessible_instance(self, db: Session, user_id: str, instance_id: str) -> Optional[Instance]:
        """A Instance ativa de id `instance_id` se o usuário acessa (regra de `app.api.access`); None, com warning, senão."""
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
        if not user:
            return None
        instance = db.query(Instance).filter(Instance.id == instance_id, Instance.is_active == True).first()  # noqa: E712
        if not instance:
            logger.warning("Realtime access to unknown instance denied", user_id=user_id, instance_id=instance_id)
            return None
        if not can_access_instance(instance, user):
            logger.warning("Realtime access to another owner's instance denied", user_id=user_id, instance_id=instance_id)
            return None
        return instance

    def _user_can_access_instance(self, user_id: str, instance_id: str) -> bool:
        """Mesma regra das rotas HTTP (`app.api.access`): dono ou superusuário; Instance desconhecida, nega."""
        db = SessionLocal()
        try:
            return self._accessible_instance(db, user_id, instance_id) is not None
        finally:
            db.close()

    def _authorized_conversation(
        self, user_id: str, instance_id: str, conversation_id: str
    ) -> Optional[Recipient]:
        """Destinatário da Conversation, ou None se a Instance for negada ou a Conversation não for dela."""
        db = SessionLocal()
        try:
            instance = self._accessible_instance(db, user_id, instance_id)
            if instance is None:
                return None
            conversation = (
                db.query(Conversation)
                .filter(Conversation.instance_id == instance.id, Conversation.id == conversation_id)
                .first()
            )
            if conversation is None:
                logger.warning(
                    "Realtime access to a conversation outside the instance denied",
                    user_id=user_id,
                    instance_id=instance_id,
                )
                return None
            return Recipient.from_conversation(instance, conversation)
        finally:
            db.close()

    async def emit_realtime_event(self, event: dict[str, Any]) -> None:
        """Entrega um evento do bus: revalida pelo schema e emite numa sala só. Evento inválido é descartado."""
        schema = EVENTS.get(str(event.get("type")))
        if schema is None:
            logger.warning("Realtime event of unknown type dropped", event_type=event.get("type"))
            return
        try:
            parsed = schema.model_validate(event.get("payload"))
        except ValidationError as exc:
            logger.warning("Realtime event with invalid payload dropped", event_type=schema.name, errors=exc.errors(include_url=False, include_context=False, include_input=False))
            return
        await self.server.emit(schema.name, parsed.model_dump(mode="json"), room=parsed.room())


def _ref(data: Any, key: str) -> Optional[str]:
    """Id (string não vazia) em `data[key]`; qualquer outra coisa vinda do cliente vale como ausente."""
    value = data.get(key) if isinstance(data, dict) else None
    return value if isinstance(value, str) and value else None


chat_socket_service = ChatSocketService()
