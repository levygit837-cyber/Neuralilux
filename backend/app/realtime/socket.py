"""
Socket.IO server used by the frontend chat to receive realtime updates.
"""

from __future__ import annotations

from typing import Any, Optional

import socketio
import structlog

from app.api.access import can_access_instance, resolve_instance
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models import User
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
            token = (auth or {}).get("token")
            user = self._get_user_from_token(token) if token else None

            if not user:
                logger.warning("Frontend socket authentication failed", sid=sid)
                return False

            await self.server.save_session(
                sid,
                {
                    "user_id": user.id,
                    "email": user.email,
                },
            )
            logger.info("Frontend socket connected", sid=sid, user_id=user.id)

        @self.server.event
        async def disconnect(sid: str):
            logger.info("Frontend socket disconnected", sid=sid)

        @self.server.on("subscribe_instance")
        async def subscribe_instance(sid: str, data: dict[str, Any]):
            session = await self.server.get_session(sid)
            user_id = session.get("user_id")
            instance_name = data.get("instanceName")
            if not instance_name or not user_id or not self._user_can_access_instance(user_id, instance_name):
                return {"ok": False}

            await self.server.enter_room(sid, self._instance_room(instance_name))
            logger.info(
                "Frontend socket subscribed to instance",
                sid=sid,
                instance_name=instance_name,
                user_id=user_id,
            )
            return {"ok": True}

        @self.server.on("leave_instance")
        async def leave_instance(sid: str, data: dict[str, Any]):
            instance_name = data.get("instanceName")
            if not instance_name:
                return {"ok": False}

            await self.server.leave_room(sid, self._instance_room(instance_name))
            return {"ok": True}

        @self.server.on("join_conversation")
        async def join_conversation(sid: str, data: dict[str, Any]):
            instance_name = data.get("instanceName")
            conversation_id = data.get("conversationId")
            if not instance_name or not conversation_id:
                return {"ok": False}

            await self.server.enter_room(
                sid,
                self._conversation_room(instance_name, conversation_id),
            )
            return {"ok": True}

        @self.server.on("leave_conversation")
        async def leave_conversation(sid: str, data: dict[str, Any]):
            instance_name = data.get("instanceName")
            conversation_id = data.get("conversationId")
            if not instance_name or not conversation_id:
                return {"ok": False}

            await self.server.leave_room(
                sid,
                self._conversation_room(instance_name, conversation_id),
            )
            return {"ok": True}

        @self.server.on("send_message")
        async def send_message(sid: str, data: dict[str, Any]):
            instance_name = data.get("instanceName")
            remote_jid = data.get("conversationId")
            content = data.get("content")

            if not instance_name or not remote_jid or not content:
                return {"ok": False}

            try:
                result = await evolution_api.send_text_message(instance_name, remote_jid, content)
                return {"ok": True, "messageId": result.get("key", {}).get("id") or result.get("id")}
            except Exception as exc:  # pragma: no cover - defensive path
                logger.error("Socket send_message failed", error=str(exc), instance_name=instance_name)
                return {"ok": False}

    def _get_user_from_token(self, token: Optional[str]) -> Optional[User]:
        if not token:
            return None

        payload = decode_access_token(token)
        if payload is None:
            return None

        email = payload.get("sub")
        if not email:
            return None

        db = SessionLocal()
        try:
            return db.query(User).filter(User.email == email, User.is_active == True).first()
        finally:
            db.close()

    def _user_can_access_instance(self, user_id: str, instance_name: str) -> bool:
        """Mesma regra das rotas HTTP (`app.api.access`): dono ou superusuário; sem Instance mapeada, nega."""
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
            if not user:
                return False
            instance = resolve_instance(db, instance_name)
            if not instance:
                logger.warning(
                    "Realtime subscription to unknown instance denied",
                    user_id=user_id,
                    instance_name=instance_name,
                )
                return False
            return can_access_instance(instance, user)
        finally:
            db.close()

    def _instance_room(self, instance_name: str) -> str:
        return f"instance:{instance_name}"

    def _conversation_room(self, instance_name: str, conversation_id: str) -> str:
        return f"conversation:{instance_name}:{conversation_id}"

    async def emit_realtime_event(self, event: dict[str, Any]) -> None:
        instance_name = event.get("instance_name")
        if not instance_name:
            return

        room = self._instance_room(instance_name)
        event_type = event.get("type")
        payload = event.get("payload", {})

        if event_type == "incoming_message":
            await self.server.emit("conversation_updated", payload.get("conversation"), room=room)
            await self.server.emit("new_message", payload.get("message"), room=room)
        elif event_type == "message_status":
            await self.server.emit("message_status_update", payload, room=room)
        elif event_type == "connection_status":
            await self.server.emit("connection_status_update", payload, room=room)
        elif event_type == "qr_code":
            await self.server.emit("qr_code_update", payload, room=room)
        elif event_type == "thinking":
            conversation_id = payload.get("conversationId") or payload.get("conversation_id")
            if conversation_id:
                normalized_payload = {
                    **payload,
                    "conversationId": conversation_id,
                    "conversation_id": conversation_id,
                    "event": payload.get("event"),
                    "data": payload.get("data", {}),
                }
                conv_room = self._conversation_room(instance_name, conversation_id)
                await self.server.emit("thinking_event", normalized_payload, room=conv_room)
                # Also emit to instance room as fallback
                await self.server.emit("thinking_event", normalized_payload, room=room)
        elif event_type == "tool_event":
            conversation_id = (
                payload.get("conversationId")
                or payload.get("conversation_id")
                or payload.get("sessionId")
                or payload.get("session_id")
            )
            if conversation_id:
                normalized_payload = {
                    **payload,
                    "conversationId": conversation_id,
                    "conversation_id": conversation_id,
                    "sessionId": payload.get("sessionId") or payload.get("session_id") or conversation_id,
                    "session_id": payload.get("sessionId") or payload.get("session_id") or conversation_id,
                    "source": payload.get("source"),
                    "phase": payload.get("phase"),
                    "error": payload.get("error"),
                    "traceId": payload.get("traceId") or payload.get("trace_id"),
                    "trace_id": payload.get("traceId") or payload.get("trace_id"),
                    "requestId": payload.get("requestId") or payload.get("request_id"),
                    "request_id": payload.get("requestId") or payload.get("request_id"),
                    "toolName": payload.get("toolName") or payload.get("tool_name"),
                    "tool_name": payload.get("toolName") or payload.get("tool_name"),
                    "displayName": payload.get("displayName") or payload.get("display_name"),
                    "display_name": payload.get("displayName") or payload.get("display_name"),
                    "inputPreview": payload.get("inputPreview") or payload.get("input_preview"),
                    "input_preview": payload.get("inputPreview") or payload.get("input_preview"),
                    "outputPreview": payload.get("outputPreview") or payload.get("output_preview"),
                    "output_preview": payload.get("outputPreview") or payload.get("output_preview"),
                    "inputPayload": payload.get("inputPayload") or payload.get("input_payload"),
                    "input_payload": payload.get("inputPayload") or payload.get("input_payload"),
                    "outputPayload": payload.get("outputPayload") or payload.get("output_payload"),
                    "output_payload": payload.get("outputPayload") or payload.get("output_payload"),
                    "startedAt": payload.get("startedAt") or payload.get("started_at"),
                    "started_at": payload.get("startedAt") or payload.get("started_at"),
                    "finishedAt": payload.get("finishedAt") or payload.get("finished_at"),
                    "finished_at": payload.get("finishedAt") or payload.get("finished_at"),
                }
                conv_room = self._conversation_room(instance_name, conversation_id)
                await self.server.emit("tool_event", normalized_payload, room=conv_room)
                await self.server.emit("tool_event", normalized_payload, room=room)
        elif event_type == "human_handoff_requested":
            conversation_id = payload.get("conversationId") or payload.get("conversation_id")
            if conversation_id:
                ticket_id = payload.get("ticketId") or payload.get("ticket_id")
                normalized_payload = {
                    **payload,
                    "conversationId": conversation_id,
                    "conversation_id": conversation_id,
                    "ticketId": ticket_id,
                    "ticket_id": ticket_id,
                    "reason": payload.get("reason"),
                }
                conv_room = self._conversation_room(instance_name, conversation_id)
                await self.server.emit("human_handoff_requested", normalized_payload, room=conv_room)
                await self.server.emit("human_handoff_requested", normalized_payload, room=room)


chat_socket_service = ChatSocketService()
