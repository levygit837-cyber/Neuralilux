"""CRUD de gateways: a chave de API nunca volta pela API; unicidade; atribuicao por agente."""
import pytest

from app.models.models import InferenceGateway

BASE = "/api/v1/gateways"


def _create_gateway(client, headers, **overrides):
    body = {"name": "Kiro-backend", "base_url": "http://localhost:5580/v1/", "api_key": "sk-super-secret"}
    body.update(overrides)
    return client.post(f"{BASE}/", json=body, headers=headers)


def _create_model(client, headers, gateway_id, **overrides):
    body = {"name": "Sonnet 5.5 (low)", "model_id": "claude-sonnet-5.5", "reasoning_effort": "low"}
    body.update(overrides)
    return client.post(f"{BASE}/{gateway_id}/models", json=body, headers=headers)


def test_requires_authentication(client):
    assert client.get(f"{BASE}/").status_code == 401


def test_api_key_is_encrypted_at_rest_and_never_returned(client, auth_headers, db):
    response = _create_gateway(client, auth_headers)

    assert response.status_code == 201
    payload = response.json()
    assert payload["has_api_key"] is True
    assert "sk-super-secret" not in response.text
    assert payload["base_url"] == "http://localhost:5580/v1"  # barra final removida

    stored = db.query(InferenceGateway).one().api_key_encrypted
    assert stored and "sk-super-secret" not in stored
    assert "sk-super-secret" not in client.get(f"{BASE}/", headers=auth_headers).text


def test_patch_api_key_semantics_keep_replace_remove(client, auth_headers, db):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    before = db.query(InferenceGateway).one().api_key_encrypted

    client.patch(f"{BASE}/{gateway_id}", json={"timeout_seconds": 30}, headers=auth_headers)
    db.expire_all()
    assert db.query(InferenceGateway).one().api_key_encrypted == before  # ausente = mantem

    client.patch(f"{BASE}/{gateway_id}", json={"api_key": "novo"}, headers=auth_headers)
    db.expire_all()
    assert db.query(InferenceGateway).one().api_key_encrypted != before  # valor = substitui

    response = client.patch(f"{BASE}/{gateway_id}", json={"api_key": ""}, headers=auth_headers)
    assert response.json()["has_api_key"] is False  # vazio = remove


@pytest.mark.parametrize("bad_url", ["localhost:5580", "ftp://x/v1", "not a url"])
def test_rejects_invalid_base_url(client, auth_headers, bad_url):
    assert _create_gateway(client, auth_headers, base_url=bad_url).status_code == 422


def test_duplicate_gateway_and_model_names_conflict(client, auth_headers):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    assert _create_gateway(client, auth_headers).status_code == 409

    assert _create_model(client, auth_headers, gateway_id).status_code == 201
    assert _create_model(client, auth_headers, gateway_id).status_code == 409


def test_invalid_reasoning_effort_is_rejected(client, auth_headers):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    assert _create_model(client, auth_headers, gateway_id, reasoning_effort="extreme").status_code == 422


def test_assignment_lifecycle_and_cascade_on_model_delete(client, auth_headers):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    model_id = _create_model(client, auth_headers, gateway_id).json()["id"]

    put = client.put(f"{BASE}/assignments/whatsapp_agent", json={"gateway_model_id": model_id}, headers=auth_headers)
    assert put.status_code == 200 and put.json()["model_id"] == "claude-sonnet-5.5"
    assert [a["agent_type"] for a in client.get(f"{BASE}/assignments", headers=auth_headers).json()] == ["whatsapp_agent"]

    assert client.delete(f"{BASE}/models/{model_id}", headers=auth_headers).status_code == 204
    assert client.get(f"{BASE}/assignments", headers=auth_headers).json() == []


def test_cannot_assign_inactive_model(client, auth_headers):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    model_id = _create_model(client, auth_headers, gateway_id, is_active=False).json()["id"]
    response = client.put(f"{BASE}/assignments/default", json={"gateway_model_id": model_id}, headers=auth_headers)
    assert response.status_code == 400


def test_unknown_agent_type_is_rejected(client, auth_headers):
    response = client.put(f"{BASE}/assignments/hacker", json={"gateway_model_id": "x"}, headers=auth_headers)
    assert response.status_code == 422


def test_deleting_gateway_removes_models_and_assignments(client, auth_headers):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    model_id = _create_model(client, auth_headers, gateway_id).json()["id"]
    client.put(f"{BASE}/assignments/default", json={"gateway_model_id": model_id}, headers=auth_headers)

    assert client.delete(f"{BASE}/{gateway_id}", headers=auth_headers).status_code == 204
    assert client.get(f"{BASE}/", headers=auth_headers).json() == []
    assert client.get(f"{BASE}/assignments", headers=auth_headers).json() == []
