"""Contexto de log por evento do worker (#94): `message_id`, `conversation_id` e `instance_id` em todo log do evento,
inclusive o das tasks do `TurnRunner`, e nada sobra depois dele."""
import json

import pytest
import structlog

from app.whatsapp.consumer import WhatsAppMessageConsumer
from app.whatsapp.evolution_client import evolution_api
from consumer_helpers import process, upsert

pytestmark = pytest.mark.asyncio


async def test_logs_of_the_turn_task_carry_the_event_ids_and_the_context_is_cleared(db, world, monkeypatch, capsys):
    async def no_id(*, instance_name, remote_jid, text):
        return {}  # o sender loga "Evolution did not return a message id" sem nenhum id próprio

    monkeypatch.setattr(evolution_api, "send_text_message", no_id)

    await process(WhatsAppMessageConsumer(), upsert(message_id="in-ctx"))

    entries = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    [warning] = [e for e in entries if e["event"] == "Evolution did not return a message id"]
    assert warning["level"] == "warning" and warning["message_id"] == "in-ctx"
    assert warning["instance_id"] == world["instance"].id and warning["conversation_id"]
    assert structlog.contextvars.get_contextvars() == {}


async def test_event_with_null_data_is_logged_with_traceback_and_raised(db, world, capsys):
    with pytest.raises(AttributeError):
        await WhatsAppMessageConsumer().process_webhook_event({"data": None})

    entries = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    [failure] = [e for e in entries if e["event"] == "Error processing webhook event"]
    assert failure["level"] == "error" and "AttributeError" in failure["exception"]
    assert structlog.contextvars.get_contextvars() == {}
