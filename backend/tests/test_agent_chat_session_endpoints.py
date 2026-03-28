import asyncio

from app.models.models import Company
from app.super_agents.memory.session_memory import SessionMemory
from app.services.menu_catalog_service import sync_macedos_menu_from_json


def test_create_agent_chat_session_returns_session_id(client, auth_headers):
    response = client.post("/api/v1/agents/chat/session", json={}, headers=auth_headers)

    assert response.status_code == 200

    payload = response.json()
    assert "session_id" in payload
    assert payload["session_id"]


def test_agent_chat_session_messages_include_persisted_thinking(client, db, auth_headers):
    session_id = client.post("/api/v1/agents/chat/session", json={}, headers=auth_headers).json()["session_id"]

    asyncio.run(
        SessionMemory.add_message(
            db=db,
            session_id=session_id,
            role="user",
            content="Quero ver meu faturamento",
        )
    )
    asyncio.run(
        SessionMemory.add_message(
            db=db,
            session_id=session_id,
            role="assistant",
            content="**Olá**\n\n1. Receita\n2. Custos",
            thinking_content="Analisando vendas e custos antes de responder.",
        )
    )

    response = client.get(f"/api/v1/agents/chat/session/{session_id}/messages", headers=auth_headers)

    assert response.status_code == 200

    payload = response.json()
    assert payload["total"] == 2
    assert [item["role"] for item in payload["items"]] == ["user", "assistant"]
    assert payload["items"][1]["thinking_content"] == "Analisando vendas e custos antes de responder."
    assert payload["items"][1]["content"] == "**Olá**\n\n1. Receita\n2. Custos"


def test_agent_chat_sessions_list_returns_recent_sessions_with_own_content(client, db, auth_headers):
    first_session_id = client.post("/api/v1/agents/chat/session", json={}, headers=auth_headers).json()["session_id"]
    second_session_id = client.post("/api/v1/agents/chat/session", json={}, headers=auth_headers).json()["session_id"]

    asyncio.run(
        SessionMemory.add_message(
            db=db,
            session_id=first_session_id,
            role="user",
            content="Quero analisar o faturamento do mês",
        )
    )
    asyncio.run(
        SessionMemory.add_message(
            db=db,
            session_id=first_session_id,
            role="assistant",
            content="Posso montar um resumo financeiro.",
            thinking_content="Revendo receitas e despesas.",
        )
    )
    asyncio.run(
        SessionMemory.add_message(
            db=db,
            session_id=second_session_id,
            role="user",
            content="Monte uma nova campanha para clientes antigos",
        )
    )

    response = client.get("/api/v1/agents/chat/sessions", headers=auth_headers)

    assert response.status_code == 200

    payload = response.json()
    assert payload["total"] >= 2

    returned_ids = [item["id"] for item in payload["items"]]
    assert second_session_id in returned_ids
    assert first_session_id in returned_ids

    second_session = next(item for item in payload["items"] if item["id"] == second_session_id)
    first_session = next(item for item in payload["items"] if item["id"] == first_session_id)

    assert second_session["title"] == "Monte uma nova campanha para clientes antigos"
    assert second_session["last_message_preview"] == "Monte uma nova campanha para clientes antigos"
    assert first_session["title"] == "Quero analisar o faturamento do mês"
    assert first_session["last_message_preview"] == "Posso montar um resumo financeiro."


def test_agent_chat_session_messages_stay_isolated_per_session(client, db, auth_headers):
    first_session_id = client.post("/api/v1/agents/chat/session", json={}, headers=auth_headers).json()["session_id"]
    second_session_id = client.post("/api/v1/agents/chat/session", json={}, headers=auth_headers).json()["session_id"]

    asyncio.run(
        SessionMemory.add_message(
            db=db,
            session_id=first_session_id,
            role="user",
            content="Mensagem da sessão A",
        )
    )
    asyncio.run(
        SessionMemory.add_message(
            db=db,
            session_id=second_session_id,
            role="user",
            content="Mensagem da sessão B",
        )
    )

    first_response = client.get(f"/api/v1/agents/chat/session/{first_session_id}/messages", headers=auth_headers)
    second_response = client.get(f"/api/v1/agents/chat/session/{second_session_id}/messages", headers=auth_headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert [item["content"] for item in first_response.json()["items"]] == ["Mensagem da sessão A"]
    assert [item["content"] for item in second_response.json()["items"]] == ["Mensagem da sessão B"]


def test_create_agent_chat_session_uses_authenticated_user_company(client, db):
    company = Company(name="Empresa Autenticada", is_active=True)
    db.add(company)
    db.commit()
    company_id = company.id

    client.post(
        "/api/v1/auth/register",
        json={
            "email": "agent-auth@example.com",
            "password": "testpass123",
            "full_name": "Agent Auth User",
            "company_id": company_id,
        },
    )
    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "agent-auth@example.com",
            "password": "testpass123",
        },
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = client.post("/api/v1/agents/chat/session", json={}, headers=headers)

    assert response.status_code == 200

    session_id = response.json()["session_id"]
    session = asyncio.run(SessionMemory.get_session(db=db, session_id=session_id))

    assert session is not None
    assert session["company_id"] == company_id


def test_agent_chat_returns_direct_menu_response_without_server_error(client, db, monkeypatch):
    def override_get_db():
        yield db

    monkeypatch.setattr("app.core.database.get_db", override_get_db)
    monkeypatch.setattr("app.super_agents.tool_runtime.get_db", override_get_db)
    monkeypatch.setattr("app.super_agents.tools.menu_tool.get_db", override_get_db)
    monkeypatch.setattr("app.super_agents.tools.whatsapp_tool.get_db", override_get_db)

    company = Company(name="Macedos", is_active=True)
    db.add(company)
    db.commit()
    sync_macedos_menu_from_json(db)

    client.post(
        "/api/v1/auth/register",
        json={
            "email": "menu-agent@example.com",
            "password": "testpass123",
            "full_name": "Menu Agent User",
            "company_id": company.id,
        },
    )
    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "menu-agent@example.com",
            "password": "testpass123",
        },
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = client.post(
        "/api/v1/agents/chat",
        json={"message": "quero ver o cardápio"},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"]
    assert "Categorias disponíveis" in payload["response"]
