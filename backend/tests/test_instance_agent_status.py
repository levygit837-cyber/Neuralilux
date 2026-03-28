import pytest

from app.models.models import Agent, Instance, User


def test_get_agent_status_creates_placeholder_instance_when_missing(client, auth_headers, db):
    response = client.get(
        "/api/v1/instances/evo-agent-status-missing/agent-status",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()
    instance = db.query(Instance).filter(
        Instance.evolution_instance_id == "evo-agent-status-missing"
    ).one()

    assert data["instance_id"] == instance.id
    assert data["instance_name"] == "evo-agent-status-missing"
    assert data["agent_enabled"] is False
    assert data["agent_id"] is None
    assert instance.agent_enabled is False


def test_patch_agent_status_creates_placeholder_instance_and_updates_flag(client, auth_headers, db):
    response = client.patch(
        "/api/v1/instances/evo-agent-status-toggle/agent-status",
        headers=auth_headers,
        json={"agent_enabled": False},
    )

    assert response.status_code == 200

    data = response.json()
    instance = db.query(Instance).filter(
        Instance.evolution_instance_id == "evo-agent-status-toggle"
    ).one()

    assert data["instance_id"] == instance.id
    assert data["instance_name"] == "evo-agent-status-toggle"
    assert data["agent_enabled"] is False
    assert instance.agent_enabled is False


def test_patch_agent_status_requires_bound_agent_to_enable(client, auth_headers, db):
    response = client.patch(
        "/api/v1/instances/evo-agent-enable-without-binding/agent-status",
        headers=auth_headers,
        json={"agent_enabled": True},
    )

    assert response.status_code == 400
    assert "Assign an agent" in response.json()["detail"]


def test_patch_agent_binding_assigns_agent_and_allows_enabling(client, auth_headers, db):
    user = db.query(User).filter(User.email == "test@example.com").one()
    agent = Agent(
        id="agent-binding-1",
        name="Agente Vinculado",
        description="Agente para testes",
        system_prompt="Teste",
        is_active=True,
        owner_id=user.id,
    )
    db.add(agent)
    db.commit()

    bind_response = client.patch(
        "/api/v1/instances/evo-agent-binding/agent-binding",
        headers=auth_headers,
        json={"agent_id": agent.id},
    )

    assert bind_response.status_code == 200
    bind_data = bind_response.json()
    assert bind_data["agent_enabled"] is False
    assert bind_data["agent_id"] == agent.id
    assert bind_data["agent_name"] == "Agente Vinculado"

    enable_response = client.patch(
        "/api/v1/instances/evo-agent-binding/agent-status",
        headers=auth_headers,
        json={"agent_enabled": True},
    )

    assert enable_response.status_code == 200
    enable_data = enable_response.json()
    instance = db.query(Instance).filter(
        Instance.evolution_instance_id == "evo-agent-binding"
    ).one()

    assert enable_data["agent_enabled"] is True
    assert enable_data["agent_id"] == agent.id
    assert enable_data["agent_name"] == "Agente Vinculado"
    assert instance.agent_id == agent.id
    assert instance.agent_enabled is True


def test_patch_agent_binding_unbinds_agent_and_disables_auto_reply(client, auth_headers, db):
    user = db.query(User).filter(User.email == "test@example.com").one()
    agent = Agent(
        id="agent-binding-2",
        name="Agente Desvinculado",
        system_prompt="Teste",
        is_active=True,
        owner_id=user.id,
    )
    instance = Instance(
        id="instance-binding-2",
        name="evo-agent-binding-2",
        evolution_instance_id="evo-agent-binding-2",
        status="connected",
        is_active=True,
        owner_id=user.id,
        agent_id=agent.id,
        agent_enabled=True,
    )
    db.add_all([agent, instance])
    db.commit()

    response = client.patch(
        "/api/v1/instances/evo-agent-binding-2/agent-binding",
        headers=auth_headers,
        json={"agent_id": None},
    )

    assert response.status_code == 200
    data = response.json()
    db.refresh(instance)

    assert data["agent_enabled"] is False
    assert data["agent_id"] is None
    assert instance.agent_id is None
    assert instance.agent_enabled is False


def test_list_agents_returns_only_active_agents_available_to_current_user(client, auth_headers, db):
    user = db.query(User).filter(User.email == "test@example.com").one()
    other_user = User(
        id="other-user-agent-list",
        email="other@example.com",
        hashed_password="hashed",
        full_name="Other User",
        is_active=True,
    )
    db.add(other_user)
    db.flush()

    visible_agent = Agent(
        id="visible-agent-1",
        name="Agente Visível",
        system_prompt="Teste",
        is_active=True,
        owner_id=user.id,
    )
    shared_agent = Agent(
        id="shared-agent-1",
        name="Agente Compartilhado",
        system_prompt="Teste",
        is_active=True,
        owner_id=None,
    )
    hidden_agent = Agent(
        id="hidden-agent-1",
        name="Agente Oculto",
        system_prompt="Teste",
        is_active=True,
        owner_id=other_user.id,
    )
    inactive_agent = Agent(
        id="inactive-agent-1",
        name="Agente Inativo",
        system_prompt="Teste",
        is_active=False,
        owner_id=user.id,
    )
    db.add_all([visible_agent, shared_agent, hidden_agent, inactive_agent])
    db.commit()

    response = client.get("/api/v1/agents/", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert {item["id"] for item in data["items"]} == {visible_agent.id, shared_agent.id}