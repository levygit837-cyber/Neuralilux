"""Acesso por dono nas rotas de /api/v1/instances (T10)."""
import pytest
from sqlalchemy.orm import sessionmaker

from app.models import Agent, Instance
from app.realtime import socket as socket_module
from app.whatsapp.evolution_client import EvolutionAPIError
from tests.access_helpers import fake_evolution, make_company, make_instance, make_user, user_id

ALREADY_IN_USE = EvolutionAPIError(
    'Evolution API returned 403: {"response":{"message":["This name \\"inst-x\\" is already in use."]}}',
    status_code=403,
)

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


def _count(db) -> int:
    return db.query(Instance).count()


# --- criação: só POST /{name}, depois que a Evolution criou ---------------------------------------------


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


def _owner(client, db, email: str) -> dict:
    """Usuário comum com Company: criar Instance exige uma (#85)."""
    return make_user(client, db, email, company=make_company(db, f"Company de {email}"))


def test_create_response_never_carries_the_evolution_instance_token(client, db, evolution):
    headers = _owner(client, db, "dono@example.com")
    evolution["create_instance"].return_value = {
        "instance": {"instanceName": "inst-novo", "status": "created"},
        "hash": "token-secreto-da-instance",
        "apikey": "token-secreto-da-instance",
    }

    response = client.post("/api/v1/instances/inst-novo", headers=headers)

    assert response.status_code == 200
    assert "token-secreto-da-instance" not in response.text
    assert "raw" not in response.json()
    assert response.json()["instance_id"] == "inst-novo"


def test_local_row_is_written_only_after_evolution_created_the_instance(client, db, evolution):
    headers = _owner(client, db, "dono@example.com")
    rows_when_evolution_ran = []

    async def create(name, *args, **kwargs):
        rows_when_evolution_ran.append(_count(db))
        return {"instance": {"instanceName": name}}

    evolution["create_instance"].side_effect = create

    assert client.post("/api/v1/instances/inst-novo", headers=headers).status_code == 200
    assert rows_when_evolution_ran == [0]
    assert _count(db) == 1


def test_create_failure_in_evolution_leaves_no_local_row(client, db, evolution):
    headers = _owner(client, db, "dono@example.com")
    evolution["create_instance"].side_effect = EvolutionAPIError("boom", status_code=500)

    response = client.post("/api/v1/instances/inst-novo", headers=headers)

    assert response.status_code == 502
    assert _count(db) == 0


def test_create_over_another_owners_instance_is_403_before_calling_evolution(client, db, two_owners, evolution):
    _, bob = two_owners
    response = client.post("/api/v1/instances/inst-alice", headers=bob)
    assert response.status_code == 403
    evolution["create_instance"].assert_not_called()


def test_regular_user_gets_409_when_evolution_already_has_the_name(client, db, evolution):
    headers = _owner(client, db, "comum@example.com")
    evolution["create_instance"].side_effect = ALREADY_IN_USE

    response = client.post("/api/v1/instances/inst-x", headers=headers)

    assert response.status_code == 409
    assert _count(db) == 0
    evolution["get_instance_qrcode"].assert_not_called()


def test_user_without_company_gets_403_before_calling_evolution(client, db, evolution):
    headers = make_user(client, db, "sem-company@example.com")

    response = client.post("/api/v1/instances/inst-novo", headers=headers)

    assert response.status_code == 403
    assert "Company" in response.json()["detail"]
    evolution["create_instance"].assert_not_called()
    assert _count(db) == 0


def test_superuser_imports_an_instance_that_already_exists_in_evolution(client, db, evolution):
    company = make_company(db, "Importada", with_agent=True)
    admin = make_user(client, db, "admin@example.com", company=company, superuser=True)
    evolution["create_instance"].side_effect = ALREADY_IN_USE

    response = client.post("/api/v1/instances/inst-x", headers=admin)

    assert response.status_code == 200
    instance = db.query(Instance).filter(Instance.evolution_instance_id == "inst-x").one()
    assert instance.owner_id == user_id(db, "admin@example.com")
    assert instance.company_id == company.id
    assert instance.agent_enabled is True


def test_concurrent_create_returns_409_and_rolls_back(client, db, evolution, monkeypatch):
    headers = _owner(client, db, "dono@example.com")
    _race_on_commit(monkeypatch)  # duas linhas com o mesmo evolution_instance_id: o commit estoura como na corrida real

    response = client.post("/api/v1/instances/inst-corrida", headers=headers)

    assert response.status_code == 409
    assert _count(db) == 0
    assert client.get("/api/v1/instances/", headers=headers).status_code == 200  # a sessão segue utilizável
    # Esta requisição criou a Instance na Evolution e a linha local não foi gravada: apaga o órfão.
    evolution["create_instance"].assert_awaited_once()
    evolution["delete_instance"].assert_awaited_once_with("inst-corrida")


def _race_on_commit(monkeypatch):
    def racing_upsert(session, name, user):
        for _ in range(2):
            instance = Instance(name=name, evolution_instance_id=name, owner_id=user.id, is_active=True)
            session.add(instance)
        return instance

    monkeypatch.setattr("app.api.routes.instances.connection.upsert_instance_for_user", racing_upsert)


def test_failed_orphan_cleanup_is_logged_and_never_masks_the_409(client, db, evolution, monkeypatch):
    headers = _owner(client, db, "dono@example.com")
    _race_on_commit(monkeypatch)
    evolution["delete_instance"].side_effect = EvolutionAPIError("boom", status_code=500)

    response = client.post("/api/v1/instances/inst-corrida", headers=headers)

    assert response.status_code == 409
    assert "created concurrently" in response.json()["detail"]
    evolution["delete_instance"].assert_awaited_once_with("inst-corrida")
    assert _count(db) == 0


def test_conflict_on_an_instance_that_already_existed_in_evolution_does_not_delete_it(client, db, evolution, monkeypatch):
    company = make_company(db, "Importada")
    admin = make_user(client, db, "admin@example.com", company=company, superuser=True)
    evolution["create_instance"].side_effect = ALREADY_IN_USE  # não foi esta requisição que a criou
    _race_on_commit(monkeypatch)

    response = client.post("/api/v1/instances/inst-x", headers=admin)

    assert response.status_code == 409
    evolution["delete_instance"].assert_not_called()


# --- Instance sem dono (legado): só o superusuário assume -----------------------------------------------


def test_unowned_instance_is_403_for_a_regular_user_on_every_route(client, db, evolution):
    company = make_company(db, "Legado", with_agent=True)
    headers = make_user(client, db, "comum@example.com", company=company)
    make_instance(db, "inst-legado", None)
    base = "/api/v1/instances/inst-legado"

    assert client.get(f"{base}/status", headers=headers).status_code == 403
    assert client.post(f"{base}/connect", headers=headers).status_code == 403
    assert client.delete(f"{base}/logout", headers=headers).status_code == 403
    assert client.delete(base, headers=headers).status_code == 403
    assert client.get(f"{base}/agent-status", headers=headers).status_code == 403
    assert client.patch(f"{base}/agent-status", json={"agent_enabled": False}, headers=headers).status_code == 403
    assert client.patch(f"{base}/agent-binding", json={"agent_id": None}, headers=headers).status_code == 403
    assert client.post(base, headers=headers).status_code == 403
    evolution["create_instance"].assert_not_called()
    instance = db.query(Instance).filter(Instance.name == "inst-legado").one()
    assert instance.owner_id is None and instance.company_id is None and instance.agent_id is None


def test_superuser_claims_unowned_instance_with_owner_company_and_agent(client, db, evolution):
    company = make_company(db, "Legado", with_agent=True)
    admin = make_user(client, db, "admin@example.com", company=company, superuser=True)
    make_instance(db, "inst-legado", None)

    response = client.post("/api/v1/instances/inst-legado", headers=admin)

    assert response.status_code == 200
    instance = db.query(Instance).filter(Instance.name == "inst-legado").one()
    assert instance.owner_id == user_id(db, "admin@example.com")
    assert instance.company_id == company.id
    assert instance.agent_id is not None and instance.agent_enabled is True


# --- o ataque: agent-status/binding nunca criam linha ---------------------------------------------------


def test_agent_status_on_a_name_without_row_is_404_and_creates_nothing(client, db, evolution):
    headers = make_user(client, db, "atacante@example.com")
    before = _count(db)

    response = client.get("/api/v1/instances/instancia-da-vitima/agent-status", headers=headers)

    assert response.status_code == 404
    assert _count(db) == before
    # Sem linha, as rotas de conexão também não alcançam a instância da Evolution.
    assert client.post("/api/v1/instances/instancia-da-vitima/connect", headers=headers).status_code == 404
    assert client.delete("/api/v1/instances/instancia-da-vitima", headers=headers).status_code == 404
    evolution["get_instance_qrcode"].assert_not_called()
    evolution["delete_instance"].assert_not_called()


def test_patch_agent_status_and_binding_on_a_name_without_row_are_404_and_create_nothing(client, db, evolution):
    headers = make_user(client, db, "atacante@example.com")

    status_resp = client.patch(
        "/api/v1/instances/instancia-da-vitima/agent-status", json={"agent_enabled": False}, headers=headers
    )
    binding_resp = client.patch(
        "/api/v1/instances/instancia-da-vitima/agent-binding", json={"agent_id": None}, headers=headers
    )

    assert status_resp.status_code == 404
    assert binding_resp.status_code == 404
    assert _count(db) == 0


def test_get_agent_status_writes_nothing_even_for_the_owner(client, db, evolution, monkeypatch):
    headers = make_user(client, db, "dono@example.com")
    make_instance(db, "inst-dono", "dono@example.com")
    commits = []
    monkeypatch.setattr(db, "commit", lambda: commits.append(1))

    response = client.get("/api/v1/instances/inst-dono/agent-status", headers=headers)

    assert response.status_code == 200
    assert commits == []
    assert not db.dirty and not db.new


# --- caminhos de sucesso das rotas de conexão -----------------------------------------------------------


def test_owner_connect_returns_the_qr_code(client, two_owners, evolution):
    alice, _ = two_owners
    response = client.post("/api/v1/instances/inst-alice/connect", headers=alice)
    assert response.status_code == 200
    body = response.json()
    assert body["qr_code"] == "qr-data"
    assert body["status"] == "connecting"
    evolution["get_instance_qrcode"].assert_awaited_once_with("inst-alice")


def test_owner_connect_on_an_already_connected_instance_has_no_qr(client, two_owners, evolution):
    alice, _ = two_owners
    evolution["get_instance_qrcode"].return_value = {}
    response = client.post("/api/v1/instances/inst-alice/connect", headers=alice)
    assert response.status_code == 200
    body = response.json()
    assert body["qr_code"] is None
    assert body["status"] == "open"
    assert "already open" in body["message"]


@pytest.mark.parametrize("evolution_status,expected", [(404, 404), (401, 401), (500, 502)])
def test_evolution_errors_map_to_http_status(client, two_owners, evolution, evolution_status, expected):
    alice, _ = two_owners
    evolution["get_instance_qrcode"].side_effect = EvolutionAPIError(
        "falhou: http://evolution:8080 apikey=segredo", status_code=evolution_status
    )
    response = client.post("/api/v1/instances/inst-alice/connect", headers=alice)
    assert response.status_code == expected
    assert response.json()["detail"] == "Evolution API error"  # o texto do upstream fica só no log


def test_owner_logout_disconnects_in_evolution(client, two_owners, evolution):
    alice, _ = two_owners
    response = client.delete("/api/v1/instances/inst-alice/logout", headers=alice)
    assert response.status_code == 200
    assert response.json()["status"] == "disconnected"
    evolution["disconnect_instance"].assert_awaited_once_with("inst-alice")


def test_delete_when_evolution_no_longer_has_it_still_deactivates_locally(client, db, two_owners, evolution):
    alice, _ = two_owners
    evolution["delete_instance"].side_effect = EvolutionAPIError("not found", status_code=404)

    response = client.delete("/api/v1/instances/inst-alice", headers=alice)

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    assert db.query(Instance).filter(Instance.name == "inst-alice").one().is_active is False


def test_delete_with_an_evolution_failure_keeps_the_local_instance(client, db, two_owners, evolution):
    alice, _ = two_owners
    evolution["delete_instance"].side_effect = EvolutionAPIError("boom", status_code=500)

    response = client.delete("/api/v1/instances/inst-alice", headers=alice)

    assert response.status_code == 502
    assert db.query(Instance).filter(Instance.name == "inst-alice").one().is_active is True


# --- Socket.IO usa a mesma regra de dono ----------------------------------------------------------------


@pytest.fixture
def socket_service(db, monkeypatch):
    monkeypatch.setattr(socket_module, "SessionLocal", sessionmaker(bind=db.get_bind()))
    return socket_module.chat_socket_service


def test_socket_subscription_follows_the_owner_rule(client, db, socket_service):
    make_user(client, db, "alice@example.com")
    make_user(client, db, "bob@example.com")
    make_user(client, db, "admin@example.com", superuser=True)
    alice_instance = make_instance(db, "inst-alice", "alice@example.com")
    legacy_instance = make_instance(db, "inst-legado", None)
    alice, bob, admin = (user_id(db, e) for e in ("alice@example.com", "bob@example.com", "admin@example.com"))

    can = socket_service._user_can_access_instance
    assert can(alice, alice_instance.id) is True
    assert can(bob, alice_instance.id) is False
    assert can(admin, alice_instance.id) is True
    assert can(alice, legacy_instance.id) is False  # sem dono: só superusuário
    assert can(bob, legacy_instance.id) is False
    assert can(admin, legacy_instance.id) is True
    assert can(alice, "nao-existe") is False  # sem Instance mapeada não há fallback
    assert can(alice, "inst-alice") is False  # o nome não resolve: só o id da Instance
    assert can("id-inexistente", alice_instance.id) is False
