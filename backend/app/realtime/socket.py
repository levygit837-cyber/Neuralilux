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
from app.core.database import SessionLocal
from app.models import Conversation, Instance, User
from app.realtime.events import EVENTS, conversation_room, instance_room
from app.services import handoff_service
from app.services.user_service import get_active_user_from_token
from app.whatsapp.evolution_client import evolution_api

logger = structlog.get_logger()


class ChatSocketService:
    def __init__(self) -> None:
        self.server = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins=settings.CORS_ORIGINS,
            logger=False,
            engineio_logger=False,
        )
        self.asgi_app = socketio.ASGIApp(self.server, socketio_path="realtime/socket.io")
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
            evolution_name, remote_jid = target

            try:
                result = await evolution_api.send_text_message(evolution_name, remote_jid, content)
                await asyncio.to_thread(self._record_attendant_activity, conversation_id)
                return {"ok": True, "messageId": result.get("key", {}).get("id") or result.get("id")}
            except Exception as exc:  # pragma: no cover - defensive path
                logger.error("Socket send_message failed", error=str(exc), instance_id=instance_id)
                return {"ok": False}

    async def _user_id(self, sid: str) -> Optional[str]:
        session = await self.server.get_session(sid)
        return session.get("user_id")

    def _record_attendant_activity(self, conversation_id: str) -> None:
        """O Attendant escreveu pelo chat: reinicia o timeout do Handoff. Falha só loga; a Message já saiu."""
        db = SessionLocal()
        try:
            conversation = db.get(Conversation, conversation_id)
            if conversation is not None:
                handoff_service.record_attendant_activity(db, conversation)
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to record attendant activity", error=str(exc))
        finally:
            db.close()

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
    ) -> Optional[tuple[str, str]]:
        """(nome na Evolution, JID) da Conversation, ou None se a Instance for negada ou a Conversation não for dela."""
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
            return instance.evolution_instance_id or instance.name, conversation.remote_jid
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
            logger.warning("Realtime event with invalid payload dropped", event_type=schema.name, error=str(exc))
            return
        await self.server.emit(schema.name, parsed.model_dump(mode="json"), room=parsed.room())


def _ref(data: Any, key: str) -> Optional[str]:
    """Id (string não vazia) em `data[key]`; qualquer outra coisa vinda do cliente vale como ausente."""
    value = data.get(key) if isinstance(data, dict) else None
    return value if isinstance(value, str) and value else None


chat_socket_service = ChatSocketService()
