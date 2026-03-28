import importlib
from decimal import Decimal

import pytest

from app.models.models import Company, MenuCategory, MenuItem
from app.services.menu_catalog_service import DEFAULT_MENU_JSON_PATH, sync_macedos_menu_from_json

cardapio_tool_module = importlib.import_module("app.agents.tools.cardapio_tool")
nodes_module = importlib.import_module("app.agents.graph.nodes")
pedido_tool_module = importlib.import_module("app.agents.tools.pedido_tool")
menu_service_module = importlib.import_module("app.services.menu_catalog_service")


def test_sync_macedos_menu_creates_company_catalog_categories_and_items(db):
    catalog = sync_macedos_menu_from_json(db, DEFAULT_MENU_JSON_PATH)

    company = db.query(Company).filter(Company.id == catalog.company_id).one()
    sopa = db.query(MenuCategory).filter(MenuCategory.catalog_id == catalog.id, MenuCategory.name == "Sopas").one()
    item = db.query(MenuItem).filter(MenuItem.catalog_id == catalog.id, MenuItem.name == "Creme de Cebola").one()

    assert company.name == "Macedos"
    assert catalog.name == "Cardápio"
    assert db.query(MenuCategory).filter(MenuCategory.catalog_id == catalog.id).count() == 14
    assert db.query(MenuItem).filter(MenuItem.catalog_id == catalog.id).count() == 166
    assert item.category_id == sopa.id
    assert item.price == Decimal("75.00")


def test_cardapio_tool_returns_real_item_from_json_when_database_is_empty(db, monkeypatch):
    monkeypatch.setattr(cardapio_tool_module, "_get_db", lambda: db)

    result = cardapio_tool_module.cardapio_tool.invoke({"query": "item:Creme de Cebola"})

    assert "Creme de Cebola" in result
    assert "Sopas" in result
    assert "R$ 75,00" in result


@pytest.mark.asyncio
async def test_plan_menu_query_uses_llm_output(monkeypatch):
    async def fake_run_json_prompt(*args, **kwargs):
        return {"query": "categoria:Sopas"}

    monkeypatch.setattr(nodes_module, "_run_json_prompt", fake_run_json_prompt)

    query = await nodes_module._plan_menu_query(
        {
            "current_message": "quero ver as sopas",
            "_history_text": "Cliente: oi",
        }
    )

    assert query == "categoria:Sopas"


@pytest.mark.asyncio
async def test_classify_intent_node_uses_llm_json_output(monkeypatch):
    async def fake_chat_completion(*args, **kwargs):
        return {"content": '{"intent":"cardapio","flow_stage":"explorando_cardapio"}'}

    monkeypatch.setattr("app.services.inference_service.inference_service.chat_completion", fake_chat_completion)

    result = await nodes_module.classify_intent_node(
        {
            "current_message": "quero pedir",
            "_history_text": "",
            "flow_stage": None,
            "coleta_etapa": None,
            "pedido_atual": None,
        }
    )

    assert result["intent"] == "cardapio"
    assert result["flow_stage"] == "explorando_cardapio"


@pytest.mark.asyncio
async def test_generate_response_returns_cardapio_directly_without_waiting():
    state = {
        "conversation_id": "conv-1",
        "instance_id": "instance-1",
        "remote_jid": "5511999999999@s.whatsapp.net",
        "contact_name": "Cliente Teste",
        "messages": [],
        "current_message": "quero ver as sopas",
        "intent": "cardapio",
        "intent_confidence": 0.9,
        "flow_stage": "explorando_cardapio",
        "cardapio_context": "🍲 *SOPAS*\n• Creme de Cebola - R$ 75,00",
        "cardapio_items": None,
        "pedido_atual": None,
        "pedido_total": None,
        "cliente_nome": None,
        "cliente_endereco": None,
        "cliente_telefone": None,
        "forma_pagamento": None,
        "coleta_etapa": None,
        "response": None,
        "output_type": None,
        "output_data": None,
        "should_respond": True,
        "error": None,
    }

    result = await nodes_module.generate_response_node(state)

    assert result["response"] == "🍲 *SOPAS*\n• Creme de Cebola - R$ 75,00"
    assert "aguarde" not in result["response"].lower()
    assert "um momento" not in result["response"].lower()


@pytest.mark.asyncio
async def test_generate_response_returns_direct_greeting():
    state = {
        "conversation_id": "conv-2",
        "instance_id": "instance-1",
        "remote_jid": "5511999999999@s.whatsapp.net",
        "contact_name": "Cliente Teste",
        "messages": [],
        "current_message": "oi",
        "intent": "saudacao",
        "intent_confidence": 0.9,
        "flow_stage": "saudacao",
        "cardapio_context": None,
        "cardapio_items": None,
        "pedido_atual": None,
        "pedido_total": None,
        "cliente_nome": None,
        "cliente_endereco": None,
        "cliente_telefone": None,
        "forma_pagamento": None,
        "coleta_etapa": None,
        "response": None,
        "output_type": None,
        "output_data": None,
        "should_respond": True,
        "error": None,
    }

    result = await nodes_module.generate_response_node(state)

    assert "cardápio" in result["response"].lower() or "categorias" in result["response"].lower()
    assert "aguarde" not in result["response"].lower()


def test_is_nemotron_model_uses_runtime_inference_model(monkeypatch):
    monkeypatch.setattr("app.services.inference_service.inference_service.model", "local-model")
    assert nodes_module._is_nemotron_model() is False

    monkeypatch.setattr("app.services.inference_service.inference_service.model", "nvidia/nemotron-3-nano-4b")
    assert nodes_module._is_nemotron_model() is True


@pytest.mark.asyncio
async def test_execute_action_handles_order_request_via_llm_plan(db, monkeypatch):
    monkeypatch.setattr(pedido_tool_module, "SessionLocal", lambda: db)
    monkeypatch.setattr(nodes_module, "SessionLocal", lambda: db)
    pedido_tool_module._pedidos_ativos.clear()
    pedido_tool_module.set_active_conversation("conv-pedido-direto")
    menu_service_module.sync_macedos_menu_from_json(db, menu_service_module.DEFAULT_MENU_JSON_PATH)

    async def fake_plan_order_action(*args, **kwargs):
        return {
            "action": "adicionar",
            "item_name": "Creme de Cebola",
            "quantity": 2,
            "observacao": "",
        }

    monkeypatch.setattr(nodes_module, "_plan_order_action", fake_plan_order_action)

    state = {
        "conversation_id": "conv-pedido-direto",
        "instance_id": "instance-1",
        "remote_jid": "5511999999999@s.whatsapp.net",
        "contact_name": "Cliente Teste",
        "messages": [],
        "current_message": "2 creme de cebola",
        "intent": "pedido",
        "intent_confidence": 0.9,
        "flow_stage": None,
        "cardapio_context": None,
        "cardapio_items": None,
        "pedido_atual": None,
        "pedido_total": None,
        "cliente_nome": None,
        "cliente_endereco": None,
        "cliente_telefone": None,
        "forma_pagamento": None,
        "coleta_etapa": None,
        "response": None,
        "output_type": None,
        "output_data": None,
        "should_respond": True,
        "error": None,
    }

    result = await nodes_module.execute_action_node(state)

    assert "Creme de Cebola" in result["cardapio_context"]
    assert "R$ 150,00" in result["cardapio_context"]


@pytest.mark.asyncio
async def test_generate_response_uses_direct_fallback_when_model_returns_blank(monkeypatch):
    async def fake_emit(*args, **kwargs):
        return None

    async def fake_stream(*args, **kwargs):
        if False:
            yield "response", ""

    monkeypatch.setattr(nodes_module, "_emit_thinking_event", fake_emit)
    monkeypatch.setattr("app.services.inference_service.inference_service.astream_chat_completion_with_thinking", fake_stream)

    state = {
        "conversation_id": "conv-3",
        "instance_id": "instance-1",
        "remote_jid": "5511999999999@s.whatsapp.net",
        "contact_name": "Cliente Teste",
        "messages": [],
        "current_message": "preciso de ajuda",
        "intent": "outro",
        "intent_confidence": 0.2,
        "flow_stage": None,
        "cardapio_context": None,
        "cardapio_items": None,
        "pedido_atual": None,
        "pedido_total": None,
        "cliente_nome": None,
        "cliente_endereco": None,
        "cliente_telefone": None,
        "forma_pagamento": None,
        "coleta_etapa": None,
        "response": None,
        "output_type": None,
        "output_data": None,
        "should_respond": True,
        "error": None,
    }

    result = await nodes_module.generate_response_node(state)

    assert "cardápio" in result["response"].lower()
