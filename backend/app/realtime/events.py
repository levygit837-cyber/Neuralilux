"""Contrato dos eventos realtime: um schema por evento, snake_case, uma sala por evento.

Quem publica constrói o schema (`app.realtime.publish.publish_event`) e a API o revalida antes de emitir
(`ChatSocketService.emit_realtime_event`), então nenhum payload sai sem passar por aqui. `instance_id` e
`conversation_id` são sempre os UUIDs: o `remote_jid` e o nome da Instance nunca viajam como identidade.

Eventos que não falam de uma Conversation (conexão e QR code) levam só `instance_id`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict


def instance_room(instance_id: str) -> str:
    return f"instance:{instance_id}"


def conversation_room(conversation_id: str) -> str:
    return f"conversation:{conversation_id}"


class RealtimeEvent(BaseModel):
    """Base: o evento Socket.IO tem o nome em `name` e vai para a sala da Instance, salvo `scope = "conversation"`."""

    model_config = ConfigDict(extra="forbid")

    name: ClassVar[str]
    scope: ClassVar[Literal["instance", "conversation"]] = "instance"

    instance_id: str

    def room(self) -> str:
        if self.scope == "conversation":
            return conversation_room(getattr(self, "conversation_id"))
        return instance_room(self.instance_id)


class ConversationEvent(RealtimeEvent):
    conversation_id: str


class ConversationUpdated(ConversationEvent):
    """A Conversation mudou na lista: última mensagem, não lidas, nome."""

    name = "conversation_updated"

    contact_name: str
    last_message: str
    timestamp: datetime
    unread_count: int
    avatar: str | None = None


class NewMessage(ConversationEvent):
    name = "new_message"

    message_id: str | None
    content: str
    timestamp: datetime
    is_outgoing: bool
    status: str
    sender_name: str | None = None


class MessageStatusUpdate(ConversationEvent):
    name = "message_status_update"

    message_id: str
    status: str


class ConnectionStatusUpdate(RealtimeEvent):
    name = "connection_status_update"

    status: str
    evolution_state: str


class QrCodeUpdate(RealtimeEvent):
    name = "qr_code_update"

    qrcode: str | dict[str, Any]


class ThinkingEvent(ConversationEvent):
    """Início e fim do Turn. Só quem abriu a Conversation (sala dela) recebe."""

    name = "thinking_event"
    scope = "conversation"

    event: Literal["thinking_start", "thinking_end"]
    data: dict[str, Any] = {}


class ToolEvent(ConversationEvent):
    """Ciclo de uma Tool do Turn. `input_payload` e `output_payload` só vêm com `TOOL_EVENT_INCLUDE_RAW_PAYLOADS`."""

    name = "tool_event"
    scope = "conversation"

    source: str
    trace_id: str
    request_id: str
    tool_name: str
    phase: Literal["waiting_input", "started", "completed", "failed"]
    display_name: str | None = None
    input_preview: str | None = None
    output_preview: str | None = None
    input_payload: Any = None
    output_payload: Any = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class HandoffUpdated(ConversationEvent):
    """Um Attendant assumiu, devolveu ou o timeout devolveu a Conversation ao Agent."""

    name = "handoff_updated"

    change: Literal["assumed", "released", "expired"]
    human_in_loop: bool
    assigned_to: str | None = None
    ticket_id: str | None = None
    timestamp: datetime


class HumanHandoffRequested(ConversationEvent):
    """O Agent abriu o Handoff pela Tool `transferir_atendente`."""

    name = "human_handoff_requested"

    ticket_id: str
    reason: str
    timestamp: datetime


EVENTS: dict[str, type[RealtimeEvent]] = {
    cls.name: cls
    for cls in (
        ConversationUpdated,
        NewMessage,
        MessageStatusUpdate,
        ConnectionStatusUpdate,
        QrCodeUpdate,
        ThinkingEvent,
        ToolEvent,
        HandoffUpdated,
        HumanHandoffRequested,
    )
}
