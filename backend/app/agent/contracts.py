"""Shared contracts for the agent core.

Types only, no logic. The LLM client (`app.llm`), the agent loop
(`app.agent.loop`), memory and every Pack import from here so they can be
built in parallel against the same shapes. Message shapes are the subset of
the Anthropic Messages protocol the agent uses.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, NotRequired, Protocol, TypedDict

from sqlalchemy.orm import Session


class TextBlock(TypedDict):
    type: Literal["text"]
    text: str


class ToolUseBlock(TypedDict):
    type: Literal["tool_use"]
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlock(TypedDict):
    type: Literal["tool_result"]
    tool_use_id: str
    content: str
    is_error: NotRequired[bool]


ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock


class ChatMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str | list[ContentBlock]


DEFAULT_MAX_TOKENS = 1024


@dataclass(frozen=True)
class MessagesRequest:
    model: str
    system: str
    messages: list[ChatMessage]
    # Each tool schema is {"name", "description", "input_schema"}.
    tools: list[dict[str, Any]] = field(default_factory=list)
    max_tokens: int = DEFAULT_MAX_TOKENS
    effort: str | None = None
    temperature: float | None = None


@dataclass(frozen=True)
class MessagesResponse:
    content: list[ContentBlock]
    stop_reason: str
    model: str
    output_tokens: int


class MessagesClient(Protocol):
    async def create(self, request: MessagesRequest) -> MessagesResponse: ...


@dataclass(frozen=True)
class ToolContext:
    """Everything a Tool handler may touch during one Turn."""

    db: Session
    company_id: str
    instance_id: str
    conversation_id: str
    contact_id: str
    remote_jid: str
    # O executor cria um ToolContext por Turn. `turn_id` distingue um Turn do seguinte; `trigger_at` é quando
    # chegou a Message do Contact que disparou o Turn (None: não informado); `turn_state` é rascunho do Turn,
    # livre para cada Pack, que o indexa pelo próprio nome (`turn_state["catalog_orders"]`) e some com o Turn.
    turn_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trigger_at: datetime | None = None
    turn_state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    content: str  # text returned to the model
    is_error: bool = False
    ends_turn: bool = False  # True: the loop stops without calling the model again (e.g. Handoff)


ToolHandler = Callable[[ToolContext, dict[str, Any]], Awaitable[ToolResult]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


class Pack(Protocol):
    """Tools and prompt instructions for one Business Type.

    A Pack MAY also define `on_session_start(db, conversation) -> None` (ADR 0007), called inside the
    transaction that stores the Message that opened a new Session (no commit). It is optional and
    deliberately not part of this Protocol: `app.agent.sessions.roll_session` looks it up with `getattr`.

    A Pack MAY also define `on_reply_delivered(db, conversation, turn_id, at) -> None`, called after the reply of
    the Turn `turn_id` was actually sent to the Contact (`app.agent.delivery`). Same rules: optional, no commit
    required beyond what the hook needs, looked up with `getattr`.
    """

    name: str

    def tools(self) -> list[Tool]: ...

    def system_prompt_section(self, ctx: ToolContext) -> str: ...
