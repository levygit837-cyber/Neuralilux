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
from typing import TYPE_CHECKING, Any, Literal, NotRequired, Protocol, TypedDict, runtime_checkable

from sqlalchemy.orm import Session

from app.llm.retry import RetryBudget

if TYPE_CHECKING:
    from app.models import Conversation


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
    # Orçamento de retry do Turn, compartilhado por todas as chamadas dele; None: a chamada tem o próprio.
    retry_budget: RetryBudget | None = None


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
    # livre para cada Pack, que o indexa pelo próprio nome (`turn_state["<nome do Pack>"]`) e some com o Turn.
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

    `system_prompt_section` is the STABLE part of the Pack's instructions: it goes in the system prompt, which must
    be byte-identical across Turns of the same Company (prefix cache, issue #42). Anything that changes between
    Turns (a note about something left unfinished, the Company's open/closed state) goes in `turn_context` instead, which the executor puts
    in the delimited block at the start of the last `user` message (`app.agent.turn_context`). Return "" for none.

    A Pack MAY also implement the optional hooks `SessionStartHook` and `ReplyDeliveredHook` below. They are
    separate Protocols so a Pack without a hook stays a valid `Pack`; the core narrows with `isinstance`
    (`app.agent.sessions.roll_session`, `app.agent.executor.reply_delivered`). Hook names are closed: `app.agent.pack_hooks`
    rejects any other `on_*` attribute when the Pack is registered, so a typo never turns into a silent no-op.
    """

    name: str

    def tools(self) -> list[Tool]: ...

    def system_prompt_section(self, ctx: ToolContext) -> str: ...

    def turn_context(self, ctx: ToolContext) -> str: ...


@runtime_checkable
class SessionStartHook(Protocol):
    """Optional Pack hook (ADR 0007): called inside the transaction that stores the Message that opened a new
    Session, with no commit."""

    def on_session_start(self, db: Session, conversation: Conversation) -> None: ...


@runtime_checkable
class ReplyDeliveredHook(Protocol):
    """Optional Pack hook: called after the reply of the Turn `turn_id` was actually sent to the Contact
    (`app.agent.executor.reply_delivered`). No commit required beyond what the hook needs."""

    def on_reply_delivered(self, db: Session, conversation: Conversation, turn_id: str, at: datetime) -> None: ...


# Closed set of hooks a Pack may define, name -> Protocol that fixes the signature. `app.agent.pack_hooks` checks
# name and signature of every `on_*` attribute at registration.
PACK_HOOKS: dict[str, type] = {
    "on_session_start": SessionStartHook,
    "on_reply_delivered": ReplyDeliveredHook,
}
