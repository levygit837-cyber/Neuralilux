from __future__ import annotations

import asyncio

import pytest

from app.super_agents.context_resolver import resolve_agent_chat_actor
from app.models.models import Company, Contact, Instance, User
from app.super_agents.memory.session_memory import SessionMemory
from app.super_agents.tool_runtime import execute_tools_for_state
from app.super_agents.tools.database_tool import _execute_database_query
from app.super_agents.tools.whatsapp_tool import list_company_contacts
from app.services.menu_catalog_service import sync_macedos_menu_from_json


def _patch_get_db(monkeypatch, db_session):
    def _get_db_override():
        yield db_session

    monkeypatch.setattr("app.super_agents.tool_runtime.get_db", _get_db_override)
    monkeypatch.setattr("app.super_agents.tools.whatsapp_tool.get_db", _get_db_override)
    monkeypatch.setattr("app.super_agents.tools.menu_tool.get_db", _get_db_override)


def _seed_company_with_contacts(db_session, company_name: str = "Empresa Teste"):
    company = Company(name=company_name, is_active=True)
    db_session.add(company)
    db_session.flush()

    user = User(
        email=f"{company_name.lower().replace(' ', '')}@example.com",
        hashed_password="secret",
        full_name="Usuário Teste",
        company_id=company.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    instance = Instance(
        name=f"{company_name}-instance",
        evolution_instance_id=f"{company_name.lower().replace(' ', '-')}-instance",
        status="connected",
        is_active=True,
        owner_id=user.id,
    )
    db_session.add(instance)
    db_session.flush()

    return company, user, instance


def _add_contact(db_session, instance: Instance, name: str, phone: str) -> Contact:
    contact = Contact(
        instance_id=instance.id,
        phone_number=phone,
        remote_jid=f"{phone}@s.whatsapp.net",
        name=name,
        push_name=name,
    )
    db_session.add(contact)
    db_session.flush()
    return contact


def test_database_query_tool_scopes_contacts_by_company(db_session):
    company_a, user_a, instance_a = _seed_company_with_contacts(db_session, "Empresa A")
    company_b, user_b, instance_b = _seed_company_with_contacts(db_session, "Empresa B")
    _add_contact(db_session, instance_a, "Maria A", "5511999990001")
    _add_contact(db_session, instance_b, "Maria B", "5511999990002")
    db_session.commit()

    payload = _execute_database_query(
        db=db_session,
        company_id=company_a.id,
        query_type="list",
        table="contacts",
        filters={},
        limit=10,
    )

    assert payload["count"] == 1
    assert payload["items"][0]["name"] == "Maria A"


@pytest.mark.asyncio
async def test_execute_tools_for_state_requires_confirmation_before_single_send(db_session, monkeypatch):
    _patch_get_db(monkeypatch, db_session)
    company, user, instance = _seed_company_with_contacts(db_session)
    _add_contact(db_session, instance, "Maria", "5511999991001")
    db_session.commit()

    state = {
        "session_id": "session-send-single",
        "company_id": company.id,
        "current_message": "envie oi para Maria",
        "intent": "whatsapp_action",
        "thinking_content": "",
        "tool_plan": {
            "mode": "whatsapp_send",
            "recipient_scope": "specific",
            "recipient_names": ["Maria"],
            "message_text": "oi",
        },
    }

    result = await execute_tools_for_state(state)

    assert result["skip_model_response"] is True
    assert result["pending_action"]["type"] == "confirm_send"
    assert len(result["pending_action"]["recipients"]) == 1
    assert "responda com 'sim'" in result["response"].lower()


@pytest.mark.asyncio
async def test_execute_tools_for_state_expands_mass_send_to_all_contacts(db_session, monkeypatch):
    _patch_get_db(monkeypatch, db_session)
    company, user, instance = _seed_company_with_contacts(db_session)
    _add_contact(db_session, instance, "Maria", "5511999992001")
    _add_contact(db_session, instance, "João", "5511999992002")
    db_session.commit()

    state = {
        "session_id": "session-send-all",
        "company_id": company.id,
        "current_message": "envie promoção para todos os contatos",
        "intent": "whatsapp_action",
        "thinking_content": "",
        "tool_plan": {
            "mode": "whatsapp_send",
            "recipient_scope": "all",
            "message_text": "promoção",
        },
    }

    result = await execute_tools_for_state(state)

    assert result["pending_action"]["type"] == "confirm_send"
    assert len(result["pending_action"]["recipients"]) == 2
    assert "Maria" in result["response"]
    assert "João" in result["response"]


@pytest.mark.asyncio
async def test_execute_tools_for_state_reads_messages_after_contact_selection(db_session, monkeypatch):
    _patch_get_db(monkeypatch, db_session)
    company, user, instance = _seed_company_with_contacts(db_session)
    _add_contact(db_session, instance, "Maria Silva", "5511999993001")
    _add_contact(db_session, instance, "Maria Souza", "5511999993002")
    session_id = await SessionMemory.create_session(
        db=db_session,
        company_id=company.id,
        user_id=user.id,
        title="Teste",
    )
    contacts = list_company_contacts(company_id=company.id, search="Maria", limit=10)

    await SessionMemory.add_message(
        db=db_session,
        session_id=session_id,
        role="assistant",
        content="Escolha o contato",
        extra_data={
            "pending_action": {
                "type": "select_contact",
                "mode": "read_messages",
                "contacts": contacts,
                "original_query": "Maria",
                "limit": 5,
            }
        },
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.super_agents.tool_runtime.read_messages_for_contact",
        lambda instance_name, remote_jid, limit=20: {
            "messages": [
                {"from_me": False, "content": f"Olá de {remote_jid}"},
                {"from_me": True, "content": "Resposta enviada"},
            ],
            "count": 2,
            "instance_name": instance_name,
            "remote_jid": remote_jid,
        },
    )

    result = await execute_tools_for_state(
        {
            "session_id": session_id,
            "company_id": company.id,
            "current_message": "2",
            "intent": "whatsapp_action",
            "thinking_content": "",
        }
    )

    assert result["pending_action"] is None
    assert "Maria Souza" in result["response"]
    assert "Resposta enviada" in result["response"]


@pytest.mark.asyncio
async def test_execute_tools_for_state_reads_messages_with_tool_plan(db_session, monkeypatch):
    _patch_get_db(monkeypatch, db_session)
    company, user, instance = _seed_company_with_contacts(db_session)
    _add_contact(db_session, instance, "João Silva", "5511999993101")
    db_session.commit()

    monkeypatch.setattr(
        "app.super_agents.tool_runtime.read_messages_for_contact",
        lambda instance_name, remote_jid, limit=20: {
            "messages": [
                {"from_me": False, "content": "Mensagem via Evolution"},
            ],
            "count": 1,
            "instance_name": instance_name,
            "remote_jid": remote_jid,
        },
    )

    result = await execute_tools_for_state(
        {
            "session_id": "session-read-natural",
            "company_id": company.id,
            "current_message": "preciso olhar esse histórico",
            "intent": "database_query",
            "thinking_content": "",
            "tool_plan": {
                "mode": "whatsapp_read_messages",
                "contact_query": "João Silva",
            },
        }
    )

    assert result["skip_model_response"] is True
    assert result["tool_calls"][0]["name"] == "whatsapp_resolve_contacts_tool"
    assert result["tool_calls"][1]["name"] == "whatsapp_read_messages_tool"
    assert "Mensagem via Evolution" in result["response"]


@pytest.mark.asyncio
async def test_execute_tools_for_state_uses_web_search_tool(db_session, monkeypatch):
    _patch_get_db(monkeypatch, db_session)
    company, user, instance = _seed_company_with_contacts(db_session)

    monkeypatch.setattr(
        "app.super_agents.tool_runtime.search_web",
        lambda query, max_results=5: {
            "query": query,
            "results": [
                {"title": "Resultado IA", "url": "https://example.com/ia"},
            ],
            "count": 1,
        },
    )

    result = await execute_tools_for_state(
        {
            "session_id": "session-web",
            "company_id": company.id,
            "current_message": "pesquise na internet sobre inteligência artificial",
            "intent": "general",
            "thinking_content": "",
            "tool_plan": {
                "mode": "web_search",
                "web_query": "inteligência artificial",
            },
        }
    )

    assert result["skip_model_response"] is True
    assert "Resultado IA" in result["response"]
    assert result["tool_calls"][0]["name"] == "web_search_tool"


@pytest.mark.asyncio
async def test_execute_tools_for_state_returns_menu_results_for_macedos(db_session, monkeypatch):
    _patch_get_db(monkeypatch, db_session)
    company, user, instance = _seed_company_with_contacts(db_session, "Macedos")
    catalog = sync_macedos_menu_from_json(db_session)
    db_session.commit()

    result = await execute_tools_for_state(
        {
            "session_id": "session-menu",
            "company_id": catalog.company_id,
            "current_message": "quero ver as sopas",
            "intent": "database_query",
            "thinking_content": "",
            "tool_plan": {
                "mode": "menu_lookup",
                "menu_category": "Sopas",
            },
        }
    )

    assert result["skip_model_response"] is True
    assert "Sopas" in result["response"] or "sopas" in result["response"].lower()
    assert "filtrando" in result["response"].lower() or "item certo" in result["response"].lower()


@pytest.mark.asyncio
async def test_execute_tools_for_state_returns_categories_for_generic_menu_request(db_session, monkeypatch):
    _patch_get_db(monkeypatch, db_session)
    company, user, instance = _seed_company_with_contacts(db_session, "Macedos")
    catalog = sync_macedos_menu_from_json(db_session)
    db_session.commit()

    result = await execute_tools_for_state(
        {
            "session_id": "session-menu-generic",
            "company_id": catalog.company_id,
            "current_message": "quero ver o cardápio",
            "intent": "database_query",
            "thinking_content": "",
            "tool_plan": {
                "mode": "menu_lookup",
            },
        }
    )

    assert result["skip_model_response"] is True
    assert "categorias" in result["response"].lower()
    assert "Sopas" in result["response"]


@pytest.mark.asyncio
async def test_execute_tools_for_state_uses_menu_query_without_runtime_shortcuts(db_session, monkeypatch):
    _patch_get_db(monkeypatch, db_session)
    company, user, instance = _seed_company_with_contacts(db_session, "Macedos")
    catalog = sync_macedos_menu_from_json(db_session)
    db_session.commit()

    result = await execute_tools_for_state(
        {
            "session_id": "session-menu-query",
            "company_id": catalog.company_id,
            "current_message": "me ajuda a decidir",
            "intent": "general",
            "thinking_content": "",
            "tool_plan": {
                "mode": "menu_lookup",
                "menu_query": "caldo",
                "menu_limit": 5,
            },
        }
    )

    assert result["skip_model_response"] is True
    assert result["tool_calls"][0]["name"] == "menu_lookup_tool"
    assert "caldo" in result["response"].lower()


@pytest.mark.asyncio
async def test_execute_tools_for_state_uses_database_search_without_runtime_shortcuts(db_session, monkeypatch):
    _patch_get_db(monkeypatch, db_session)
    company, user, instance = _seed_company_with_contacts(db_session)
    _add_contact(db_session, instance, "Maria Financeiro", "5511999994101")
    db_session.commit()

    result = await execute_tools_for_state(
        {
            "session_id": "session-db-search",
            "company_id": company.id,
            "current_message": "quero confirmar um nome",
            "intent": "general",
            "thinking_content": "",
            "tool_plan": {
                "mode": "database_query",
                "db_table": "contacts",
                "db_query_type": "search",
                "db_filters": {"q": "Maria"},
                "db_limit": 5,
            },
        }
    )

    assert result["skip_model_response"] is True
    assert result["tool_calls"][0]["name"] == "database_query_tool"
    assert "Maria Financeiro" in result["response"]


@pytest.mark.asyncio
async def test_execute_tools_for_state_resolves_menu_plan_for_bebidas_without_runtime_error(db_session, monkeypatch):
    _patch_get_db(monkeypatch, db_session)
    company, user, instance = _seed_company_with_contacts(db_session, "Macedos")
    catalog = sync_macedos_menu_from_json(db_session)
    db_session.commit()

    async def _fake_chat_completion(*args, **kwargs):
        return {
            "content": """
            {
              "mode": "menu_lookup",
              "menu_category": "Bebidas",
              "menu_limit": 6
            }
            """
        }

    monkeypatch.setattr(
        "app.super_agents.tool_runtime.inference_service.chat_completion",
        _fake_chat_completion,
    )

    result = await execute_tools_for_state(
        {
            "session_id": "session-menu-bebidas",
            "company_id": catalog.company_id,
            "current_message": "pode me falar sobre as bebidas?",
            "intent": "general",
            "thinking_content": "",
            "messages": [],
        }
    )

    assert result["skip_model_response"] is True
    assert result["tool_calls"][0]["name"] == "menu_lookup_tool"
    assert "bebidas" in result["response"].lower()


def test_list_company_contacts_falls_back_to_live_evolution_contacts(db_session, monkeypatch):
    _patch_get_db(monkeypatch, db_session)
    company, user, instance = _seed_company_with_contacts(db_session)
    db_session.commit()

    async def _fake_fetch_contacts(self, instance_name):
        return [
            {
                "id": "contact-live-1",
                "name": "Cliente Live",
                "number": "5511999994001",
                "remoteJid": "5511999994001@s.whatsapp.net",
            }
        ]

    monkeypatch.setattr(
        "app.super_agents.tools.whatsapp_tool.EvolutionAPIService.fetch_contacts",
        _fake_fetch_contacts,
    )

    contacts = list_company_contacts(company_id=company.id, search="Cliente Live", limit=10)

    assert len(contacts) == 1
    assert contacts[0]["display_name"] == "Cliente Live"
    assert contacts[0]["remote_jid"] == "5511999994001@s.whatsapp.net"


def test_list_company_contacts_prefers_live_evolution_contacts_over_persisted_contacts(
    db_session, monkeypatch
):
    _patch_get_db(monkeypatch, db_session)
    company, user, instance = _seed_company_with_contacts(db_session)
    _add_contact(db_session, instance, "Maria DB", "5511999994001")
    db_session.commit()

    fetch_calls = []

    async def _fake_fetch_contacts(self, instance_name):
        fetch_calls.append(instance_name)
        return [
            {
                "id": "contact-live-1",
                "name": "Maria Evolution",
                "pushName": "Maria Evolution",
                "number": "5511999994001",
                "remoteJid": "5511999994001@s.whatsapp.net",
            }
        ]

    monkeypatch.setattr(
        "app.super_agents.tools.whatsapp_tool.EvolutionAPIService.fetch_contacts",
        _fake_fetch_contacts,
    )

    contacts = list_company_contacts(company_id=company.id, search="Maria", limit=10)

    assert fetch_calls == [instance.evolution_instance_id]
    assert len(contacts) == 1
    assert contacts[0]["display_name"] == "Maria Evolution"
    assert contacts[0]["notes"] == "live_evolution_contact"


@pytest.mark.asyncio
async def test_execute_tools_for_state_confirm_send_uses_evolution_api(db_session, monkeypatch):
    _patch_get_db(monkeypatch, db_session)
    company, user, instance = _seed_company_with_contacts(db_session)
    contact = _add_contact(db_session, instance, "Maria", "5511999994101")
    instance_name = instance.evolution_instance_id
    remote_jid = contact.remote_jid
    session_id = await SessionMemory.create_session(
        db=db_session,
        company_id=company.id,
        user_id=user.id,
        title="Envio pendente",
    )

    await SessionMemory.add_message(
        db=db_session,
        session_id=session_id,
        role="assistant",
        content="Confirmar envio",
        extra_data={
            "pending_action": {
                "type": "confirm_send",
                "message": "oi",
                "recipients": [
                    {
                        "display_name": "Maria",
                        "instance_name": instance_name,
                        "remote_jid": remote_jid,
                    }
                ],
                "company_id": company.id,
            }
        },
    )
    db_session.commit()

    send_calls = []

    async def _fake_send_text_message(self, instance_name, remote_jid, text):
        send_calls.append((instance_name, remote_jid, text))
        return {"key": {"id": "msg-123"}}

    monkeypatch.setattr(
        "app.super_agents.tools.whatsapp_tool.EvolutionAPIService.send_text_message",
        _fake_send_text_message,
    )

    result = await execute_tools_for_state(
        {
            "session_id": session_id,
            "company_id": company.id,
            "current_message": "sim",
            "intent": "whatsapp_action",
            "thinking_content": "",
        }
    )

    assert send_calls == [(instance_name, remote_jid, "oi")]
    assert result["pending_action"] is None
    assert result["tool_calls"][0]["name"] == "whatsapp_send_message_tool"


def test_resolve_agent_chat_actor_prefers_session_context(db_session):
    company_a, user_a, instance_a = _seed_company_with_contacts(db_session, "Empresa Sessão A")
    company_b, user_b, instance_b = _seed_company_with_contacts(db_session, "Empresa Sessão B")
    created_session_id = asyncio.run(
        SessionMemory.create_session(
            db=db_session,
            company_id=company_b.id,
            user_id=user_b.id,
            title="Sessão B",
        )
    )

    resolved_company_id, resolved_user_id = resolve_agent_chat_actor(
        db=db_session,
        company_id=company_a.id,
        user_id=user_a.id,
        session_id=created_session_id,
    )

    assert resolved_company_id == company_b.id
    assert resolved_user_id == user_b.id
