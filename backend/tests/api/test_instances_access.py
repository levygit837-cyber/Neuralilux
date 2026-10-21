"""Acesso por dono nas rotas de /api/v1/instances (T10)."""
import pytest

from app.models import Agent, Instance
from tests.access_helpers import fake_evolution, make_company, make_instance, make_user, user_id

ROUTES = [
    ("get", "/api/v1/instances/"),
    ("get", "/api/v1/instances/inst-x/status"),
    ("post", "/api/v1/instances/inst-x/connect"),
    ("delete", "/api/v1/instances/inst-x/logout"),
    ("delete", "/api/v1/instances/inst-x"),
    ("post", "/api/v1/instances/inst-x"),
    ("get", "/api/v1/instances/inst-x/agent-status"),
    ("patch", "/api/v1/instances/inst-x/agent-status"),
    ("patch", "/api/v1/instances/inst-x/agent-binding"),
]


@pytest.fixture
def evolution(monkeypatch):
    return fake_evolution(monkeypatch)


@pytest.mark.parametrize("method,path", ROUTES)
def test_instance_routes_require_login(client, evolution, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401
    evolution["fetch_instances"].assert_not_called()


@pytest.fixture
def two_owners(client, db, evolution):
    alice = make_user(client, db, "alice@example.com")
    bob = make_user(client, db, "bob@example.com")
    make_instance(db, "inst-alice", "alice@example.com")
    make_instance(db, "inst-bob", "bob@example.com")
    return alice, bob


def test_status_of_another_owners_instance_is_403(client, two_owners, evolution):
    _, bob = two_owners
    response = client.get("/api/v1/instances/inst-alice/status", headers=bob)
    assert response.status_code == 403
    evolution["get_instance_status"].assert_not_called()


def test_owner_reads_status_by_name(client, two_owners, evolution):
    alice, _ = two_owners
    response = client.get("/api/v1/instances/inst-alice/status", headers=alice)
    assert response.status_code == 200
    assert response.json()["status"] == "connected"
    evolution["get_instance_status"].assert_awaited_once_with("inst-alice")


def test_unknown_instance_is_404(client, two_owners, evolution):
    alice, _ = two_owners
    assert client.get("/api/v1/instances/nope/status", headers=alice).status_code == 404


def test_connect_and_logout_of_another_owners_instance_are_403(client, two_owners, evolution):
    _, bob = two_owners
    assert client.post("/api/v1/instances/inst-alice/connect", headers=bob).status_code == 403
    assert client.delete("/api/v1/instances/inst-alice/logout", headers=bob).status_code == 403
    evolution["get_instance_qrcode"].assert_not_called()
    evolution["disconnect_instance"].assert_not_called()


def test_delete_of_another_owners_instance_is_403_and_keeps_it(client, db, two_owners, evolution):
    _, bob = two_owners
    response = client.delete("/api/v1/instances/inst-alice", headers=bob)
    assert response.status_code == 403
    evolution["delete_instance"].assert_not_called()
    assert db.query(Instance).filter(Instance.name == "inst-alice").one().is_active is True


def test_owner_delete_removes_in_evolution_and_deactivates_locally(client, db, two_owners, evolution):
    alice, _ = two_owners
    response = client.delete("/api/v1/instances/inst-alice", headers=alice)
    assert response.status_code == 200
    evolution["delete_instance"].assert_awaited_once_with("inst-alice")
    assert db.query(Instance).filter(Instance.name == "inst-alice").one().is_active is False


def test_superuser_reaches_any_instance(client, db, two_owners, evolution):
    admin = make_user(client, db, "admin@example.com", superuser=True)
    assert client.get("/api/v1/instances/inst-alice/status", headers=admin).status_code == 200
    assert client.get("/api/v1/instances/inst-bob/status", headers=admin).status_code == 200


@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/v1/instances/inst-alice/agent-status", None),
    ("patch", "/api/v1/instances/inst-alice/agent-status", {"agent_enabled": False}),
    ("patch", "/api/v1/instances/inst-alice/agent-binding", {"agent_id": None}),
])
def test_agent_routes_of_another_owners_instance_are_403_without_changes(client, db, two_owners, method, path, body):
    _, bob = two_owners
    before = db.query(Instance).filter(Instance.name == "inst-alice").one().agent_id
    kwargs = {"json": body} if body is not None else {}
    response = getattr(client, method)(path, headers=bob, **kwargs)
    assert response.status_code == 403
    db.expire_all()
    alice_instance = db.query(Instance).filter(Instance.name == "inst-alice").one()
    assert alice_instance.owner_id == user_id(db, "alice@example.com")
    assert alice_instance.agent_id == before


def test_list_returns_only_own_instances_and_never_the_evolution_token(client, db, monkeypatch):
    fake_evolution(monkeypatch, instances=[
        {"name": "inst-alice", "connectionStatus": "open", "token": "secret-alice"},
        {"name": "inst-bob", "connectionStatus": "close", "token": "secret-bob"},
        {"name": "inst-stranger", "connectionStatus": "open", "token": "secret-x"},
    ])
    alice = make_user(client, db, "alice@example.com")
    bob = make_user(client, db, "bob@example.com")
    admin = make_user(client, db, "admin@example.com", superuser=True)
    make_instance(db, "inst-alice", "alice@example.com")
    make_instance(db, "inst-bob", "bob@example.com")

    response = client.get("/api/v1/instances/", headers=alice)
    assert response.status_code == 200
    body = response.json()
    assert [i["name"] for i in body["instances"]] == ["inst-alice"]
    assert body["instances"][0]["status"] == "open"
    assert "secret" not in response.text and "token" not in response.text

    assert [i["name"] for i in client.get("/api/v1/instances/", headers=bob).json()["instances"]] == ["inst-bob"]
    admin_names = {i["name"] for i in client.get("/api/v1/instances/", headers=admin).json()["instances"]}
    assert admin_names == {"inst-alice", "inst-bob"}


def test_create_upserts_local_instance_with_owner_company_and_company_agent(client, db, evolution):
    company = make_company(db, "Pizzaria", with_agent=True)
    headers = make_user(client, db, "dono@example.com", company=company)

    response = client.post("/api/v1/instances/inst-novo", headers=headers)

    assert response.status_code == 200
    evolution["create_instance"].assert_awaited_once()
    instance = db.query(Instance).filter(Instance.evolution_instance_id == "inst-novo").one()
    agent = db.query(Agent).filter(Agent.company_id == company.id).one()
    assert instance.owner_id == user_id(db, "dono@example.com")
    assert instance.company_id == company.id
    assert instance.agent_id == agent.id
    assert instance.agent_enabled is True


def test_create_without_company_agent_leaves_agent_unset(client, db, evolution):
    company = make_company(db, "Sem Agent")
    headers = make_user(client, db, "dono@example.com", company=company)

    assert client.post("/api/v1/instances/inst-novo", headers=headers).status_code == 200

    instance = db.query(Instance).filter(Instance.name == "inst-novo").one()
    assert instance.company_id == company.id
    assert instance.agent_id is None
    assert instance.agent_enabled is False


def test_create_over_another_owners_instance_is_403_before_calling_evolution(client, db, two_owners, evolution):
    _, bob = two_owners
    response = client.post("/api/v1/instances/inst-alice", headers=bob)
    assert response.status_code == 403
    evolution["create_instance"].assert_not_called()


def test_agent_status_claims_unowned_legacy_instance_and_sets_company_agent(client, db, evolution):
    company = make_company(db, "Legado", with_agent=True)
    headers = make_user(client, db, "dono@example.com", company=company)
    make_instance(db, "inst-legado", None)

    response = client.get("/api/v1/instances/inst-legado/agent-status", headers=headers)

    assert response.status_code == 200
    instance = db.query(Instance).filter(Instance.name == "inst-legado").one()
    assert instance.owner_id == user_id(db, "dono@example.com")
    assert instance.company_id == company.id
    assert instance.agent_id is not None and instance.agent_enabled is True
    assert response.json()["agent_enabled"] is True


def test_agent_binding_unbind_survives_later_requests(client, db, evolution):
    company = make_company(db, "Desvinculo", with_agent=True)
    headers = make_user(client, db, "dono@example.com", company=company)
    client.post("/api/v1/instances/inst-a", headers=headers)

    client.patch("/api/v1/instances/inst-a/agent-binding", json={"agent_id": None}, headers=headers)
    response = client.get("/api/v1/instances/inst-a/agent-status", headers=headers)

    assert response.json()["agent_id"] is None
    assert response.json()["agent_enabled"] is False
