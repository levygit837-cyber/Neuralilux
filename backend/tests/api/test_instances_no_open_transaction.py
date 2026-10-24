"""As rotas de Instance não seguram a conexão do pool durante a chamada à Evolution (#93, ADR 0009).

A fase de banco copia o que precisa e termina com `rollback()`; a chamada de rede roda com a Session fora de
transação. Sem isso, requests suspensas na Evolution ocupam o pool e as fases de banco das outras esperam conexão.
"""
import pytest

from app.models import Instance
from tests.access_helpers import fake_evolution, make_company, make_instance, make_user


@pytest.fixture
def owner(client, db, monkeypatch):
    company = make_company(db, "Pizzaria")
    headers = make_user(client, db, "dono@example.com", company=company)
    make_instance(db, "inst-dono", "dono@example.com", company=company)
    return headers, fake_evolution(monkeypatch, instances=[{"name": "inst-dono", "connectionStatus": "open"}])


def _spy(evolution, method, db, seen):
    """Registra se a Session estava em transação quando a rota chamou a Evolution."""
    original = evolution[method].side_effect
    default = evolution[method].return_value

    async def spy(*args, **kwargs):
        seen.append(db.in_transaction())
        if original is not None:
            return await original(*args, **kwargs)
        return default

    evolution[method].side_effect = spy


@pytest.mark.parametrize(
    "http,path,method",
    [
        ("get", "/api/v1/instances/", "fetch_instances"),
        ("get", "/api/v1/instances/inst-dono/status", "get_instance_status"),
        ("post", "/api/v1/instances/inst-dono/connect", "get_instance_qrcode"),
        ("delete", "/api/v1/instances/inst-dono/logout", "disconnect_instance"),
        ("delete", "/api/v1/instances/inst-dono", "delete_instance"),
        ("post", "/api/v1/instances/inst-nova", "create_instance"),
    ],
)
def test_session_is_out_of_transaction_during_the_evolution_call(client, db, owner, http, path, method):
    headers, evolution = owner
    seen: list[bool] = []
    _spy(evolution, method, db, seen)

    response = getattr(client, http)(path, headers=headers)

    assert response.status_code == 200
    assert seen == [False]


def test_list_returns_the_local_fields_copied_before_the_rollback(client, db, owner):
    headers, _ = owner

    body = client.get("/api/v1/instances/", headers=headers).json()

    [item] = body["instances"]
    row = db.query(Instance).filter(Instance.name == "inst-dono").one()
    assert (item["id"], item["owner_id"], item["agent_enabled"]) == (row.id, row.owner_id, bool(row.agent_enabled))
    assert item["status"] == "open"


def test_delete_still_deactivates_the_local_row_after_the_rollback(client, db, owner):
    headers, _ = owner

    assert client.delete("/api/v1/instances/inst-dono", headers=headers).status_code == 200

    db.expire_all()
    row = db.query(Instance).filter(Instance.name == "inst-dono").one()
    assert (row.is_active, row.agent_enabled, row.status) == (False, False, "disconnected")
