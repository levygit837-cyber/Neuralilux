from app.models import Agent, Instance, User
from tests.access_helpers import make_company, make_instance, make_user, user_id


def _own_instance(db, name: str) -> Instance:
    user = db.query(User).filter(User.email == "test@example.com").one()
    instance = Instance(
        name=name,
        evolution_instance_id=name,
        status="disconnected",
        is_active=True,
        owner_id=user.id,
        agent_enabled=False,
    )
    db.add(instance)
    db.commit()
    return instance


def test_get_agent_status_returns_the_owners_instance_without_writing(client, auth_headers, db):
    instance = _own_instance(db, "evo-agent-status-get")

    response = client.get("/api/v1/instances/evo-agent-status-get/agent-status", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["instance_id"] == instance.id
    assert data["instance_name"] == "evo-agent-status-get"
    assert data["agent_enabled"] is False
    assert data["agent_id"] is None
    assert not db.dirty and not db.new


def test_patch_agent_status_requires_bound_agent_to_enable(client, auth_headers, db):
    _own_instance(db, "evo-agent-enable-without-binding")

    response = client.patch(
        "/api/v1/instances/evo-agent-enable-without-binding/agent-status",
        headers=auth_headers,
        json={"agent_enabled": True},
    )

    assert response.status_code == 400
    assert "Assign an agent" in response.json()["detail"]


def _company_agent(db, company, name="Agente Vinculado", **extra) -> Agent:
    agent = Agent(name=name, system_prompt="Teste", company_id=company.id, is_active=True, **extra)
    db.add(agent)
    db.commit()
    return agent


def test_patch_agent_binding_assigns_agent_and_allows_enabling(client, db):
    company = make_company(db, "Pizzaria")
    headers = make_user(client, db, "dono@example.com", company=company)
    agent = _company_agent(db, company, description="Agente para testes")
    make_instance(db, "evo-agent-binding", "dono@example.com", company, agent_enabled=False)

    bind_response = client.patch(
        "/api/v1/instances/evo-agent-binding/agent-binding", headers=headers, json={"agent_id": agent.id}
    )

    assert bind_response.status_code == 200
    bind_data = bind_response.json()
    assert bind_data["agent_enabled"] is False
    assert bind_data["agent_id"] == agent.id
    assert bind_data["agent_name"] == "Agente Vinculado"

    enable_response = client.patch(
        "/api/v1/instances/evo-agent-binding/agent-status", headers=headers, json={"agent_enabled": True}
    )

    assert enable_response.status_code == 200
    enable_data = enable_response.json()
    instance = db.query(Instance).filter(Instance.evolution_instance_id == "evo-agent-binding").one()

    assert enable_data["agent_enabled"] is True
    assert enable_data["agent_id"] == agent.id
    assert enable_data["agent_name"] == "Agente Vinculado"
    assert instance.agent_id == agent.id
    assert instance.agent_enabled is True


def test_binding_an_agent_of_another_company_is_404_even_without_owner(client, db):
    mine = make_company(db, "Minha")
    other = make_company(db, "Alheia")
    headers = make_user(client, db, "dono@example.com", company=mine)
    foreign = _company_agent(db, other, name="Agente Alheio", owner_id=None)
    instance = make_instance(db, "evo-foreign-bind", "dono@example.com", mine)

    response = client.patch(
        "/api/v1/instances/evo-foreign-bind/agent-binding", headers=headers, json={"agent_id": foreign.id}
    )

    assert response.status_code == 404
    db.refresh(instance)
    assert instance.agent_id is None


def test_binding_an_agent_of_the_users_company_that_belongs_to_someone_else_works(client, db):
    company = make_company(db, "Pizzaria")
    headers = make_user(client, db, "dono@example.com", company=company)
    colleague = make_user(client, db, "colega@example.com", company=company)
    assert colleague
    agent = _company_agent(db, company, owner_id=user_id(db, "colega@example.com"))
    make_instance(db, "evo-colleague-agent", "dono@example.com", company)

    response = client.patch(
        "/api/v1/instances/evo-colleague-agent/agent-binding", headers=headers, json={"agent_id": agent.id}
    )

    assert response.status_code == 200
    assert response.json()["agent_id"] == agent.id


def test_enabling_a_bound_agent_that_is_from_another_company_is_rejected(client, db):
    mine = make_company(db, "Minha")
    other = make_company(db, "Alheia")
    headers = make_user(client, db, "dono@example.com", company=mine)
    foreign = _company_agent(db, other)
    instance = make_instance(
        db, "evo-legacy-foreign", "dono@example.com", mine, agent_id=foreign.id, agent_enabled=False
    )

    response = client.patch(
        "/api/v1/instances/evo-legacy-foreign/agent-status", headers=headers, json={"agent_enabled": True}
    )

    assert response.status_code == 400
    db.refresh(instance)
    assert instance.agent_enabled is False


def test_superuser_binds_the_agent_of_the_instances_company(client, db):
    company = make_company(db, "Pizzaria")
    admin = make_user(client, db, "admin@example.com", superuser=True)
    agent = _company_agent(db, company)
    make_instance(db, "evo-admin-bind", "admin@example.com", company)

    response = client.patch("/api/v1/instances/evo-admin-bind/agent-binding", headers=admin, json={"agent_id": agent.id})

    assert response.status_code == 200
    assert response.json()["agent_id"] == agent.id


def test_superuser_cannot_bind_an_agent_of_another_company_to_the_instance(client, db):
    # 404, como para o usuário comum: para esta Instance o Agent alheio não existe. O superusuário ganha acesso a
    # qualquer Instance, não a vínculo que o Turn ignoraria.
    instance_company = make_company(db, "Da Instance")
    other = make_company(db, "Alheia")
    admin = make_user(client, db, "admin@example.com", superuser=True)
    foreign = _company_agent(db, other, name="Agente Alheio")
    instance = make_instance(db, "evo-admin-foreign", "admin@example.com", instance_company)

    response = client.patch("/api/v1/instances/evo-admin-foreign/agent-binding", headers=admin, json={"agent_id": foreign.id})

    assert response.status_code == 404
    db.refresh(instance)
    assert instance.agent_id is None


def test_status_of_a_legacy_instance_shows_the_company_agent_the_turn_would_use(client, db):
    company = make_company(db, "Pizzaria")
    headers = make_user(client, db, "dono@example.com", company=company)
    agent = _company_agent(db, company, name="Atendente da Company")
    instance = make_instance(db, "evo-legacy-status", "dono@example.com", company, agent_enabled=True)

    response = client.get("/api/v1/instances/evo-legacy-status/agent-status", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert (data["agent_enabled"], data["agent_id"], data["agent_name"]) == (True, agent.id, "Atendente da Company")
    db.refresh(instance)
    assert instance.agent_id is None  # o GET não grava o vínculo
    assert not db.dirty and not db.new


def test_status_follows_the_turn_when_the_bound_agent_is_from_another_company(client, db):
    mine = make_company(db, "Minha")
    headers = make_user(client, db, "dono@example.com", company=mine)
    own = _company_agent(db, mine, name="Meu")
    foreign = _company_agent(db, make_company(db, "Alheia"), name="Alheio")
    make_instance(db, "evo-stale-bind", "dono@example.com", mine, agent_id=foreign.id, agent_enabled=True)

    data = client.get("/api/v1/instances/evo-stale-bind/agent-status", headers=headers).json()

    assert (data["agent_enabled"], data["agent_id"]) == (True, own.id)


def test_status_without_any_usable_agent_is_off_even_when_enabled(client, db):
    company = make_company(db, "Sem Agent")
    headers = make_user(client, db, "dono@example.com", company=company)
    make_instance(db, "evo-no-agent", "dono@example.com", company, agent_enabled=True)

    data = client.get("/api/v1/instances/evo-no-agent/agent-status", headers=headers).json()

    assert (data["agent_enabled"], data["agent_id"], data["agent_name"]) == (False, None, None)


def test_enabling_a_legacy_instance_uses_the_company_agent_fallback(client, db):
    company = make_company(db, "Pizzaria")
    headers = make_user(client, db, "dono@example.com", company=company)
    agent = _company_agent(db, company)
    make_instance(db, "evo-legacy-enable", "dono@example.com", company, agent_enabled=False)

    response = client.patch("/api/v1/instances/evo-legacy-enable/agent-status", headers=headers, json={"agent_enabled": True})

    assert response.status_code == 200
    assert (response.json()["agent_enabled"], response.json()["agent_id"]) == (True, agent.id)


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


def test_unbinding_in_a_company_turns_replies_off_and_shows_the_agent_the_turn_would_fall_back_to(client, db):
    company = make_company(db, "Pizzaria")
    headers = make_user(client, db, "dono@example.com", company=company)
    agent = _company_agent(db, company)
    instance = make_instance(db, "evo-unbind-company", "dono@example.com", company, agent_id=agent.id, agent_enabled=True)

    data = client.patch("/api/v1/instances/evo-unbind-company/agent-binding", headers=headers, json={"agent_id": None}).json()

    db.refresh(instance)
    assert (instance.agent_id, instance.agent_enabled) == (None, False)
    assert (data["agent_enabled"], data["agent_id"]) == (False, agent.id)


def test_list_agents_returns_only_active_agents_of_the_users_company(client, db):
    mine = make_company(db, "Minha")
    other = make_company(db, "Alheia")
    headers = make_user(client, db, "dono@example.com", company=mine)
    visible = _company_agent(db, mine, name="Visível", owner_id=None)
    _company_agent(db, mine, name="Inativo").is_active = False
    _company_agent(db, other, name="De outra Company sem dono", owner_id=None)
    db.add(Agent(name="Sem Company", system_prompt="Teste", is_active=True, owner_id=None))
    db.commit()

    response = client.get("/api/v1/agents/", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert [item["id"] for item in data["items"]] == [visible.id]


def test_list_agents_for_a_user_without_company_is_empty(client, db):
    company = make_company(db, "Pizzaria")
    _company_agent(db, company)
    headers = make_user(client, db, "sem-company@example.com")

    response = client.get("/api/v1/agents/", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_superuser_lists_the_active_agents_of_every_company(client, db):
    first = _company_agent(db, make_company(db, "Primeira"), name="A")
    second = _company_agent(db, make_company(db, "Segunda"), name="B")
    admin = make_user(client, db, "admin@example.com", superuser=True)

    response = client.get("/api/v1/agents/", headers=admin)

    assert {item["id"] for item in response.json()["items"]} == {first.id, second.id}
