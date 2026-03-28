import importlib
import json
import sys
import types
from pathlib import Path

import pytest

from app.models.models import Company, Contact, Conversation, Instance, User
from app.services.menu_catalog_service import sync_macedos_menu_from_json
from app.services.order_service import (
    add_item_to_order,
    begin_checkout,
    confirm_order,
    get_active_order,
    update_customer_field,
)

pedido_tool_module = importlib.import_module("app.agents.tools.pedido_tool")
menu_service_module = importlib.import_module("app.services.menu_catalog_service")


def _seed_conversation(db_session) -> Conversation:
    company = Company(name="Empresa Pedido", is_active=True)
    db_session.add(company)
    db_session.flush()

    user = User(
        email="pedido@example.com",
        hashed_password="secret",
        full_name="Usuario Pedido",
        company_id=company.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    instance = Instance(
        name="instancia-pedido",
        evolution_instance_id="instancia-pedido",
        status="connected",
        is_active=True,
        owner_id=user.id,
    )
    db_session.add(instance)
    db_session.flush()

    contact = Contact(
        instance_id=instance.id,
        phone_number="5511999999999",
        remote_jid="5511999999999@s.whatsapp.net",
        name="Cliente Pedido",
        push_name="Cliente Pedido",
    )
    db_session.add(contact)
    db_session.flush()

    conversation = Conversation(
        instance_id=instance.id,
        contact_id=contact.id,
        remote_jid=contact.remote_jid,
        is_active=True,
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    return conversation


def _import_nodes_module(monkeypatch):
    fake_redis_asyncio = types.ModuleType("redis.asyncio")

    class _FakeRedis:
        @classmethod
        def from_url(cls, *args, **kwargs):
            return cls()

        async def publish(self, *args, **kwargs):
            return None

        async def aclose(self):
            return None

    fake_redis_asyncio.Redis = _FakeRedis
    fake_redis = types.ModuleType("redis")
    fake_redis.asyncio = fake_redis_asyncio
    monkeypatch.setitem(sys.modules, "redis", fake_redis)
    monkeypatch.setitem(sys.modules, "redis.asyncio", fake_redis_asyncio)
    return importlib.import_module("app.agents.graph.nodes")


@pytest.mark.asyncio
async def test_plan_order_action_uses_llm_payload_for_item_and_quantity(db_session, monkeypatch):
    nodes_module = _import_nodes_module(monkeypatch)
    monkeypatch.setattr(pedido_tool_module, "SessionLocal", lambda: db_session)
    pedido_tool_module._pedidos_ativos.clear()
    sync_macedos_menu_from_json(db_session, menu_service_module.DEFAULT_MENU_JSON_PATH)
    conversation = _seed_conversation(db_session)
    pedido_tool_module.set_active_conversation(conversation.id)

    async def fake_run_json_prompt(*args, **kwargs):
        return {
            "action": "adicionar",
            "item_name": "Creme de Cebola",
            "quantity": 2,
            "observacao": "",
        }

    monkeypatch.setattr(nodes_module, "_run_json_prompt", fake_run_json_prompt)

    result = await nodes_module._plan_order_action(
        {
            "current_message": "2 creme de cebola",
            "_history_text": "",
            "pedido_atual": [],
            "coleta_etapa": None,
        }
    )

    assert result["action"] == "adicionar"
    assert result["item_name"] == "Creme de Cebola"
    assert result["quantity"] == 2


def test_pedido_tool_consultar_exibe_comanda_aberta_com_numero(db_session, monkeypatch):
    monkeypatch.setattr(pedido_tool_module, "SessionLocal", lambda: db_session)
    pedido_tool_module._pedidos_ativos.clear()
    sync_macedos_menu_from_json(db_session, menu_service_module.DEFAULT_MENU_JSON_PATH)
    conversation = _seed_conversation(db_session)
    pedido_tool_module.set_active_conversation(conversation.id)

    pedido_tool_module.pedido_tool.invoke(
        {
            "acao": "adicionar",
            "item_nome": "Creme de Cebola",
            "quantidade": 1,
        }
    )

    consulta = pedido_tool_module.pedido_tool.invoke({"acao": "consultar"})

    assert "COMANDA" in consulta.upper()
    assert "PEDIDO #" in consulta.upper()
    assert "Creme de Cebola" in consulta


@pytest.mark.asyncio
async def test_load_context_node_carrega_comanda_persistida_do_banco(db_session, monkeypatch):
    nodes_module = _import_nodes_module(monkeypatch)
    monkeypatch.setattr(nodes_module, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(nodes_module, "load_conversation_history", lambda conversation_id, limit=10: [])
    monkeypatch.setattr(pedido_tool_module, "SessionLocal", lambda: db_session)
    pedido_tool_module._pedidos_ativos.clear()
    sync_macedos_menu_from_json(db_session, menu_service_module.DEFAULT_MENU_JSON_PATH)
    conversation = _seed_conversation(db_session)

    add_item_to_order(
        db=db_session,
        conversation_id=conversation.id,
        item_name="Creme de Cebola",
        quantity=2,
    )
    pedido_tool_module._pedidos_ativos.clear()

    state = await nodes_module.load_context_node(
        {
            "conversation_id": conversation.id,
            "instance_id": "instance-1",
            "remote_jid": conversation.remote_jid,
            "contact_name": "Cliente Pedido",
            "messages": [],
            "current_message": "meu pedido",
        }
    )

    assert state["pedido_atual"] is not None
    assert state["pedido_atual"][0]["nome"] == "Creme de Cebola"
    assert state["pedido_total"] == 150.0


def test_confirmar_pedido_fecha_comanda_e_gera_json(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(pedido_tool_module, "SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.services.order_service.ORDERS_OUTPUT_DIR", tmp_path)
    pedido_tool_module._pedidos_ativos.clear()
    sync_macedos_menu_from_json(db_session, menu_service_module.DEFAULT_MENU_JSON_PATH)
    conversation = _seed_conversation(db_session)

    add_item_to_order(
        db=db_session,
        conversation_id=conversation.id,
        item_name="Creme de Cebola",
        quantity=1,
    )
    begin_checkout(db_session, conversation.id)
    update_customer_field(db_session, conversation.id, "nome", "João Silva")
    update_customer_field(db_session, conversation.id, "endereco", "Rua A, 123")
    update_customer_field(db_session, conversation.id, "telefone", "(11) 99999-0000")
    update_customer_field(db_session, conversation.id, "pagamento", "PIX")

    order = get_active_order(db_session, conversation.id)
    assert order is not None
    assert order.status == "ready_for_confirmation"

    closed_order = confirm_order(db_session, conversation.id)

    assert closed_order.status == "closed"
    assert closed_order.export_path is not None

    export_file = Path(closed_order.export_path)
    assert export_file.exists()

    payload = json.loads(export_file.read_text(encoding="utf-8"))
    assert payload["status"] == "closed"
    assert payload["cliente_nome"] == "João Silva"
    assert payload["forma_pagamento"] == "PIX"
    assert payload["itens"][0]["nome"] == "Creme de Cebola"


@pytest.mark.asyncio
async def test_execute_action_node_coleta_dados_avanca_ate_confirmacao(db_session, monkeypatch):
    nodes_module = _import_nodes_module(monkeypatch)
    monkeypatch.setattr(nodes_module, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(pedido_tool_module, "SessionLocal", lambda: db_session)
    pedido_tool_module._pedidos_ativos.clear()
    sync_macedos_menu_from_json(db_session, menu_service_module.DEFAULT_MENU_JSON_PATH)
    conversation = _seed_conversation(db_session)

    add_item_to_order(
        db=db_session,
        conversation_id=conversation.id,
        item_name="Creme de Cebola",
        quantity=1,
    )
    begin_checkout(db_session, conversation.id)

    state = {
        "conversation_id": conversation.id,
        "instance_id": "instance-1",
        "remote_jid": conversation.remote_jid,
        "contact_name": "Cliente Pedido",
        "messages": [],
        "intent": "coleta_dados",
        "intent_confidence": 0.9,
        "flow_stage": "coletando_dados",
        "cardapio_context": None,
        "cardapio_items": None,
        "pedido_atual": None,
        "pedido_total": None,
        "cliente_nome": None,
        "cliente_endereco": None,
        "cliente_telefone": None,
        "forma_pagamento": None,
        "response": None,
        "output_type": None,
        "output_data": None,
        "should_respond": True,
        "error": None,
    }

    resultado_nome = await nodes_module.execute_action_node(
        {
            **state,
            "current_message": "João Silva",
            "coleta_etapa": "nome",
        }
    )
    assert "endereço" in resultado_nome["cardapio_context"].lower()

    resultado_endereco = await nodes_module.execute_action_node(
        {
            **state,
            "current_message": "Rua A, 123",
            "coleta_etapa": "endereco",
        }
    )
    assert "telefone" in resultado_endereco["cardapio_context"].lower()

    resultado_telefone = await nodes_module.execute_action_node(
        {
            **state,
            "current_message": "(11) 99999-0000",
            "coleta_etapa": "telefone",
        }
    )
    assert "pagar" in resultado_telefone["cardapio_context"].lower()

    resultado_pagamento = await nodes_module.execute_action_node(
        {
            **state,
            "current_message": "PIX",
            "coleta_etapa": "pagamento",
        }
    )
    assert "confirmar" in resultado_pagamento["cardapio_context"].lower()
