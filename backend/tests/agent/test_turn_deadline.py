"""Prazos do Turn: o Turn inteiro (`TURN_TIMEOUT_SECONDS`) e cada Tool (`TOOL_TIMEOUT_SECONDS`).

Gateway e Tools lentos de verdade (esperam num Event que nunca é solto): o que se confere é que o prazo cancela
a chamada em voo e deixa a Session do Turn sem transação aberta.
"""
import asyncio
import time
from unittest.mock import MagicMock

import pytest

from app.agent import executor
from app.agent.contracts import Tool, ToolContext, ToolResult
from app.agent.loop import run_turn
from app.agent.tools import TOOL_TIMEOUT_ERROR, ToolRegistry
from app.core.config import settings
from app.models import Company, Message
from tests.agent.test_agent_executor import _handle, agent, turn_setup  # noqa: F401  (fixtures)
from tests.agent_fakes import FakeMessagesClient, FakePack, reply, text, tool_use

HISTORY = [{"role": "user", "content": "oi"}]
MARGIN = 1.0


class SlowGateway:
    """Gateway que nunca responde; guarda se a chamada em voo foi cancelada."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False

    async def create(self, request):
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


@pytest.mark.asyncio
async def test_slow_gateway_gets_the_fallback_within_the_turn_timeout(turn_setup, agent, monkeypatch):  # noqa: F811
    db, conversation, contact, instance = turn_setup
    monkeypatch.setattr(settings, "TURN_TIMEOUT_SECONDS", 0.3)
    gateway = agent["client"] = SlowGateway()

    started = time.monotonic()
    result = await _handle(db, conversation, contact, instance, "oi")
    elapsed = time.monotonic() - started

    assert result.reply_text == executor.FALLBACK_REPLY
    assert result.turn_id is None  # nenhum Pack valida nada de um Turn vencido
    assert 0.3 <= elapsed < 0.3 + MARGIN
    assert gateway.cancelled  # a chamada ao Gateway foi cancelada de verdade, não só abandonada


@pytest.mark.asyncio
async def test_external_cancellation_propagates_without_fallback_or_stored_message(turn_setup, agent):  # noqa: F811
    db, conversation, contact, instance = turn_setup
    gateway = agent["client"] = SlowGateway()
    task = asyncio.create_task(_handle(db, conversation, contact, instance, "oi"))
    await asyncio.wait_for(gateway.started.wait(), timeout=2)  # o Turn está dentro da chamada ao Gateway

    task.cancel()  # o worker em shutdown, não o prazo do Turn
    with pytest.raises(asyncio.CancelledError):
        await task

    assert gateway.cancelled
    assert task.cancelled()  # nada devolveu um TurnResult: o consumer não envia FALLBACK_REPLY
    db.expire_all()
    assert db.query(Message).filter(Message.content == executor.FALLBACK_REPLY).count() == 0


@pytest.mark.asyncio
async def test_turn_timeout_cancels_the_tool_in_flight_and_leaves_no_open_transaction(turn_setup, agent, monkeypatch):  # noqa: F811
    db, conversation, contact, instance = turn_setup
    monkeypatch.setattr(settings, "TURN_TIMEOUT_SECONDS", 0.3)
    monkeypatch.setattr(settings, "TOOL_TIMEOUT_SECONDS", 30.0)
    company_id = instance.company_id
    state = {"cancelled": False}

    async def hangs_with_a_pending_write(ctx, args):
        ctx.db.add(Company(name="Rascunho do Turn"))
        ctx.db.flush()  # a Session fica com transação aberta e uma linha não commitada
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            state["cancelled"] = True
            raise
        return ToolResult(content="nunca")

    agent["add_tool"]("travada", hangs_with_a_pending_write)
    agent["client"] = FakeMessagesClient([reply(tool_use("travada", {}, "t1"))])

    result = await _handle(db, conversation, contact, instance, "oi")

    assert result.reply_text == executor.FALLBACK_REPLY
    assert state["cancelled"]
    assert not db.in_transaction()
    assert db.query(Company).filter(Company.name == "Rascunho do Turn").count() == 0
    assert db.get(Company, company_id) is not None


@pytest.mark.asyncio
async def test_a_slow_tool_becomes_is_error_with_rollback_and_the_turn_goes_on(monkeypatch):
    monkeypatch.setattr(settings, "TOOL_TIMEOUT_SECONDS", 0.05)
    db = MagicMock()
    ctx = ToolContext(db=db, company_id="c", instance_id="i", conversation_id="v", contact_id="p", remote_jid="j")
    state = {"cancelled": False}

    async def slow(ctx, args):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            state["cancelled"] = True
            raise
        return ToolResult(content="nunca")

    registry = ToolRegistry.from_packs([FakePack("p", [Tool("lenta", "d", {"type": "object"}, slow)])])
    client = FakeMessagesClient([reply(tool_use("lenta", {}, "t1")), reply(text("Sem essa informação agora."))])

    result = await run_turn(client, "m", "s", list(HISTORY), registry, ctx)

    assert result.reply_text == "Sem essa informação agora."
    [call] = result.tool_calls
    assert call.is_error
    assert call.result["content"] == TOOL_TIMEOUT_ERROR
    assert state["cancelled"]
    db.rollback.assert_called_once()
    tool_result = client.requests[1].messages[-1]["content"][0]
    assert tool_result["is_error"] is True


@pytest.mark.asyncio
async def test_a_tool_inside_its_deadline_is_untouched(monkeypatch):
    monkeypatch.setattr(settings, "TOOL_TIMEOUT_SECONDS", 5.0)
    db = MagicMock()
    ctx = ToolContext(db=db, company_id="c", instance_id="i", conversation_id="v", contact_id="p", remote_jid="j")

    async def quick(ctx, args):
        await asyncio.sleep(0)
        return ToolResult(content="pronto")

    registry = ToolRegistry.from_packs([FakePack("p", [Tool("rapida", "d", {"type": "object"}, quick)])])

    call = await registry.execute(ctx, tool_use("rapida", {}, "t1"))

    assert not call.is_error
    assert call.result["content"] == "pronto"
    db.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_all_gateway_calls_of_a_turn_share_one_retry_budget():
    client = FakeMessagesClient([reply(tool_use("t", {}, "t1")), reply(text("ok"))])

    async def handler(ctx, args):
        return ToolResult(content="x")

    ctx = ToolContext(db=MagicMock(), company_id="c", instance_id="i", conversation_id="v", contact_id="p", remote_jid="j")
    registry = ToolRegistry.from_packs([FakePack("p", [Tool("t", "d", {"type": "object"}, handler)])])

    await run_turn(client, "m", "s", list(HISTORY), registry, ctx)

    first, second = client.requests
    assert first.retry_budget is not None
    assert first.retry_budget is second.retry_budget
