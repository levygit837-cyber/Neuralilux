"""Recapitulação do Order só vale depois de a resposta chegar ao Contact (#32), pelo caminho real do consumer.

Executor, Pack `catalog_orders` e consumer reais; só o Gateway (roteirizado) e o envio da Evolution são falsos.
"""
import asyncio
from datetime import datetime, timezone

import pytest
from agent_fakes import FakeMessagesClient, reply, text, tool_use
from consumer_helpers import JID, process, upsert
from pack_helpers import add_item, fill_delivery, make_world, order_of, tool_named

from app.agent import executor
from app.agent.contracts import MessagesRequest
from app.core.config import settings
from app.models import Agent, BusinessType, Conversation
from app.packs.catalog_orders import checkout
from app.packs.catalog_orders.pack import CatalogOrdersPack
from app.whatsapp import consumer as consumer_module
from app.whatsapp.consumer import WhatsAppMessageConsumer
from app.whatsapp.evolution_client import evolution_api
from tests.conftest import TestingSessionLocal

pytestmark = pytest.mark.asyncio

RECAP = tool_use("gerenciar_pedido", {"acao": "recapitular"}, "t1")
FINALIZE = tool_use("gerenciar_pedido", {"acao": "finalizar"}, "t2")
OPEN_NOW = datetime(2026, 10, 19, 23, 0, tzinfo=timezone.utc)  # segunda 20:00 em Fortaleza: aberto


class FailingAfter:
    """Gateway que responde `script` e depois levanta, como um timeout no meio do Turn."""

    def __init__(self, script):
        self.inner = FakeMessagesClient(script)

    async def create(self, request: MessagesRequest):
        if not self.inner.script:
            raise RuntimeError("Gateway timeout")
        return await self.inner.create(request)


class HangingAfter:
    """Gateway que responde `script` e depois trava, como um modelo que nunca termina."""

    def __init__(self, script):
        self.inner = FakeMessagesClient(script)

    async def create(self, request: MessagesRequest):
        if not self.inner.script:
            await asyncio.Event().wait()
        return await self.inner.create(request)


class HandoffDuringTurn(FakeMessagesClient):
    """Um Attendant assume a Conversation enquanto o modelo ainda responde."""

    async def create(self, request: MessagesRequest):
        if len(self.script) == 1:
            other = TestingSessionLocal()
            try:
                other.query(Conversation).update({"human_in_loop": True})
                other.commit()
            finally:
                other.close()
        return await super().create(request)


@pytest.fixture
def shop(db, monkeypatch):
    """Company com um Order pronto para recapitular, Agent ligado e envio registrado."""
    w = make_world(db)
    business_type = BusinessType(name="Restaurante", slug="restaurant")
    db.add(business_type)
    db.flush()
    w.company.business_type_id = business_type.id
    agent = Agent(name="Atendente", system_prompt="", company_id=w.company.id, is_active=True)
    db.add(agent)
    w.instance.agent_enabled = True
    db.commit()

    sent: list[str] = []
    state = {"fail_send": False, "client": None}

    async def fake_send(*, instance_name, remote_jid, text):
        if state["fail_send"]:
            raise ConnectionError("Evolution fora do ar")
        sent.append(text)
        return {"key": {"id": f"out-{len(sent)}"}}

    async def no_summary(conversation_id):
        return None

    monkeypatch.setattr(executor, "resolve_gateway", lambda agent_type: (state["client"], "fake-model", "low"))
    monkeypatch.setattr(executor, "refresh_summary", no_summary)
    monkeypatch.setattr(evolution_api, "send_text_message", fake_send)
    monkeypatch.setattr(consumer_module, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(checkout, "utc_now", lambda: OPEN_NOW)
    w.sent, w.state = sent, state
    return w


async def _ready_order(shop):
    pedido = tool_named(CatalogOrdersPack().tools(), "gerenciar_pedido")
    await add_item(shop, pedido, quantidade=2)
    await fill_delivery(shop, pedido)


def _inbound(shop, message_id, body, offset=0):
    # Timestamp inteiro e no futuro próximo: tem de ser posterior ao instante em que a resposta saiu.
    ts = int(datetime.now(timezone.utc).timestamp()) + 5 + offset
    return upsert(text=body, remote_jid=shop.contact.remote_jid, message_id=message_id, instance="evo-loja", ts=ts)


async def _confirm_and_get_status(shop, consumer):
    """O Contact confirma e o modelo tenta `finalizar`: devolve se o Order fechou."""
    shop.state["client"] = FakeMessagesClient([reply(FINALIZE), reply(text("ok"))])
    await process(consumer, _inbound(shop, "in-confirm", "confirmo", offset=10))
    return order_of(shop).status


async def test_recap_delivered_then_confirmed_closes_the_order(shop):
    await _ready_order(shop)
    consumer = WhatsAppMessageConsumer()
    shop.state["client"] = FakeMessagesClient([reply(RECAP), reply(text("Confere? Total R$ 95,00"))])
    await process(consumer, _inbound(shop, "in-1", "nome Maria, dinheiro, pode fechar"))
    assert shop.sent == ["Confere? Total R$ 95,00"]
    assert order_of(shop).status == "open"

    assert await _confirm_and_get_status(shop, consumer) == "closed"


async def test_turn_that_fails_after_recapitular_does_not_leave_a_valid_recap(shop):
    await _ready_order(shop)
    consumer = WhatsAppMessageConsumer()
    shop.state["client"] = FailingAfter([reply(RECAP)])  # timeout do Gateway depois da Tool
    await process(consumer, _inbound(shop, "in-1", "pode fechar"))
    assert shop.sent == [executor.FALLBACK_REPLY]  # o Contact só viu a resposta fixa de erro, nunca a recapitulação

    assert await _confirm_and_get_status(shop, consumer) != "closed"


async def test_turn_that_times_out_after_recapitular_does_not_leave_a_valid_recap(shop, monkeypatch):
    monkeypatch.setattr(settings, "TURN_TIMEOUT_SECONDS", 0.3)
    await _ready_order(shop)
    consumer = WhatsAppMessageConsumer()
    shop.state["client"] = HangingAfter([reply(RECAP)])  # a Recap foi montada, mas o modelo não termina a resposta
    await process(consumer, _inbound(shop, "in-1", "pode fechar"))
    assert shop.sent == [executor.FALLBACK_REPLY]  # só o fallback saiu; a Recap nunca chegou ao Contact

    assert await _confirm_and_get_status(shop, consumer) != "closed"


async def test_turn_without_reply_does_not_leave_a_valid_recap(shop):
    await _ready_order(shop)
    consumer = WhatsAppMessageConsumer()
    shop.state["client"] = FakeMessagesClient([reply(RECAP), reply()])  # o modelo não escreve texto
    await process(consumer, _inbound(shop, "in-1", "pode fechar"))
    assert shop.sent == []

    assert await _confirm_and_get_status(shop, consumer) != "closed"


async def test_send_failure_does_not_leave_a_valid_recap(shop):
    await _ready_order(shop)
    consumer = WhatsAppMessageConsumer()
    shop.state["client"] = FakeMessagesClient([reply(RECAP), reply(text("Confere? Total R$ 95,00"))])
    shop.state["fail_send"] = True
    await process(consumer, _inbound(shop, "in-1", "pode fechar"))
    assert shop.sent == []

    shop.state["fail_send"] = False
    assert await _confirm_and_get_status(shop, consumer) != "closed"


async def test_reply_dropped_by_handoff_does_not_leave_a_valid_recap(shop):
    await _ready_order(shop)
    consumer = WhatsAppMessageConsumer()
    shop.state["client"] = HandoffDuringTurn([reply(RECAP), reply(text("Confere? Total R$ 95,00"))])
    await process(consumer, _inbound(shop, "in-1", "pode fechar"))
    assert shop.sent == []

    other = TestingSessionLocal()
    try:
        other.query(Conversation).update({"human_in_loop": False})  # Attendant devolveu a Conversation
        other.commit()
    finally:
        other.close()
    assert await _confirm_and_get_status(shop, consumer) != "closed"


async def test_confirmation_sent_before_the_recap_reached_the_contact_does_not_close(shop):
    await _ready_order(shop)
    consumer = WhatsAppMessageConsumer()
    shop.state["client"] = FakeMessagesClient([reply(RECAP), reply(text("Confere? Total R$ 95,00"))])
    await process(consumer, _inbound(shop, "in-1", "pode fechar"))
    assert len(shop.sent) == 1

    shop.state["client"] = FakeMessagesClient([reply(FINALIZE), reply(text("ok"))])
    early = upsert(
        text="pode fechar", remote_jid=JID.replace("5511999990001", shop.contact.phone_number),
        message_id="in-early", instance="evo-loja", ts=int(datetime.now(timezone.utc).timestamp()) - 60,
    )
    await process(consumer, early)  # chegou antes de a recapitulação sair
    assert order_of(shop).status == "open"
