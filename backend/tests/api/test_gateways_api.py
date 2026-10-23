"""CRUD de Gateways: so superuser escreve/testa (SSRF), a chave de API nunca volta, unicidade, atribuicao."""
import httpx
import pytest

from app.llm import registry
from app.llm.client import GatewayMessagesClient
from app.models import InferenceGateway, User

BASE = "/api/v1/gateways"


def _login(client, db, email: str, *, superuser: bool) -> dict:
    client.post("/api/v1/auth/register", json={"email": email, "password": "testpass123", "full_name": "Teste"})
    db.query(User).filter(User.email == email).update({"is_superuser": superuser})
    db.commit()
    token = client.post("/api/v1/auth/login", data={"username": email, "password": "testpass123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers(client, db):
    """Superuser autenticado; sobrescreve o fixture global porque quase toda rota daqui e de escrita."""
    return _login(client, db, "admin@example.com", superuser=True)


@pytest.fixture
def user_headers(client, db):
    """Usuario comum autenticado (nao superuser)."""
    return _login(client, db, "user@example.com", superuser=False)


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


# --- autorizacao: Gateways sao globais e `base_url` e alvo de SSRF ------------- #

def test_non_superuser_cannot_create_gateway(client, user_headers, db):
    response = _create_gateway(client, user_headers)

    assert response.status_code == 403
    assert db.query(InferenceGateway).count() == 0


def test_non_superuser_is_forbidden_on_every_mutation_and_probe(client, auth_headers, user_headers):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    model_id = _create_model(client, auth_headers, gateway_id).json()["id"]

    attempts = [
        client.patch(f"{BASE}/{gateway_id}", json={"timeout_seconds": 5}, headers=user_headers),
        client.delete(f"{BASE}/{gateway_id}", headers=user_headers),
        client.post(f"{BASE}/{gateway_id}/models", json={"name": "x", "model_id": "x"}, headers=user_headers),
        client.patch(f"{BASE}/models/{model_id}", json={"name": "y"}, headers=user_headers),
        client.delete(f"{BASE}/models/{model_id}", headers=user_headers),
        client.put(f"{BASE}/assignments/default", json={"gateway_model_id": model_id}, headers=user_headers),
        client.delete(f"{BASE}/assignments/default", headers=user_headers),
        client.post(f"{BASE}/models/{model_id}/test", headers=user_headers),
        client.get(f"{BASE}/{gateway_id}/remote-models", headers=user_headers),
    ]

    assert [r.status_code for r in attempts] == [403] * len(attempts)
    assert client.get(f"{BASE}/{gateway_id}", headers=auth_headers).json()["timeout_seconds"] == 60


def test_non_superuser_can_still_read_gateways_without_secrets(client, auth_headers, user_headers):
    _create_gateway(client, auth_headers)

    response = client.get(f"{BASE}/", headers=user_headers)

    assert response.status_code == 200 and len(response.json()) == 1
    assert "sk-super-secret" not in response.text


@pytest.mark.parametrize(
    "bad_url",
    ["http://user:pass@169.254.169.254/", "https://admin@internal.test/v1", "file:///etc/passwd", "gopher://x/"],
)
def test_base_url_rejects_userinfo_and_non_http_schemes(client, auth_headers, bad_url):
    assert _create_gateway(client, auth_headers, base_url=bad_url).status_code == 422

    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    response = client.patch(
        f"{BASE}/{gateway_id}", json={"base_url": bad_url, "api_key": "novo"}, headers=auth_headers
    )
    assert response.status_code == 422


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_gateway_name_must_not_be_blank_after_strip(client, auth_headers, blank):
    assert _create_gateway(client, auth_headers, name=blank).status_code == 422

    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    assert client.patch(f"{BASE}/{gateway_id}", json={"name": blank}, headers=auth_headers).status_code == 422


def test_gateway_name_is_stored_stripped(client, auth_headers):
    assert _create_gateway(client, auth_headers, name="  Kiro  ").json()["name"] == "Kiro"


# --- trocar base_url nao pode mandar a chave salva para outro host ------------ #

def test_changing_base_url_without_new_api_key_is_rejected(client, auth_headers, db):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    before = db.query(InferenceGateway).one().api_key_encrypted

    response = client.patch(f"{BASE}/{gateway_id}", json={"base_url": "http://evil.test"}, headers=auth_headers)

    assert response.status_code == 422
    # Mesmo formato dos erros de validacao do FastAPI: o frontend mostra a mensagem no campo `api_key`.
    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["body", "api_key"] and "api_key" in detail[0]["msg"]
    db.expire_all()
    gateway = db.query(InferenceGateway).one()
    assert gateway.base_url == "http://localhost:5580/v1" and gateway.api_key_encrypted == before


def test_changing_base_url_with_new_api_key_replaces_both(client, auth_headers, db):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    before = db.query(InferenceGateway).one().api_key_encrypted

    response = client.patch(
        f"{BASE}/{gateway_id}", json={"base_url": "http://novo.test", "api_key": "sk-novo"}, headers=auth_headers
    )

    assert response.status_code == 200 and response.json()["base_url"] == "http://novo.test"
    db.expire_all()
    assert db.query(InferenceGateway).one().api_key_encrypted != before


def test_changing_base_url_with_explicit_empty_api_key_erases_the_saved_key(client, auth_headers):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]

    response = client.patch(
        f"{BASE}/{gateway_id}", json={"base_url": "http://novo.test", "api_key": ""}, headers=auth_headers
    )

    assert response.status_code == 200 and response.json()["has_api_key"] is False


# --- probe e listagem de modelos usam o protocolo Messages ------------------- #

@pytest.fixture
def mock_gateway(monkeypatch):
    """Faz `registry.build_client` devolver um cliente sobre `httpx.MockTransport`."""
    box = {"requests": [], "handler": lambda r: httpx.Response(500), "build_kwargs": []}

    def build(gateway, **kwargs):
        box["build_kwargs"].append(kwargs)

        def handle(request):
            box["requests"].append(request)
            return box["handler"](request)

        return GatewayMessagesClient(
            base_url=gateway.base_url,
            api_key="k",
            gateway_name=gateway.name,
            backoff_seconds=0,
            transport=httpx.MockTransport(handle),
            **kwargs,
        )

    monkeypatch.setattr(registry, "build_client", build)
    return box


def test_model_probe_calls_v1_messages_with_max_tokens_8(client, auth_headers, mock_gateway):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    model_id = _create_model(client, auth_headers, gateway_id).json()["id"]
    mock_gateway["handler"] = lambda r: httpx.Response(
        200,
        json={
            "content": [{"type": "text", "text": "pong"}],
            "stop_reason": "end_turn",
            "model": "claude-sonnet-5.5",
            "usage": {"output_tokens": 1},
        },
    )

    response = client.post(f"{BASE}/models/{model_id}/test", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True and body["content"] == "pong" and body["latency_ms"] >= 0
    request = mock_gateway["requests"][0]
    assert request.url.path == "/v1/messages"
    payload = __import__("json").loads(request.content)
    assert payload["max_tokens"] == 8 and payload["model"] == "claude-sonnet-5.5"
    assert payload["output_config"] == {"effort": "low"}


def test_model_probe_reports_gateway_failure_as_not_ok(client, auth_headers, mock_gateway):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    model_id = _create_model(client, auth_headers, gateway_id).json()["id"]
    mock_gateway["handler"] = lambda r: httpx.Response(401, text="bad key")

    body = client.post(f"{BASE}/models/{model_id}/test", headers=auth_headers).json()

    assert body["ok"] is False and "HTTP 401" in body["error"]


def test_remote_models_reads_v1_models(client, auth_headers, mock_gateway):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    mock_gateway["handler"] = lambda r: httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}]})

    response = client.get(f"{BASE}/{gateway_id}/remote-models", headers=auth_headers)

    assert response.json() == {"models": ["a", "b"]}
    assert mock_gateway["requests"][0].url.path == "/v1/models"


def test_remote_models_404_falls_back_to_registered_models(client, auth_headers, mock_gateway):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    _create_model(client, auth_headers, gateway_id, name="a", model_id="claude-sonnet-5.5")
    _create_model(client, auth_headers, gateway_id, name="b", model_id="claude-opus-5")
    mock_gateway["handler"] = lambda r: httpx.Response(404, text="not found")

    response = client.get(f"{BASE}/{gateway_id}/remote-models", headers=auth_headers)

    assert response.status_code == 200
    assert sorted(response.json()["models"]) == ["claude-opus-5", "claude-sonnet-5.5"]


def test_remote_models_other_errors_are_bad_gateway(client, auth_headers, mock_gateway):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    mock_gateway["handler"] = lambda r: httpx.Response(403, text="no")

    assert client.get(f"{BASE}/{gateway_id}/remote-models", headers=auth_headers).status_code == 502


# --- origem (scheme + netloc), nao a URL inteira, decide se a chave salva precisa ser reenviada ---- #

def test_changing_only_the_path_keeps_saved_api_key_without_resending_it(client, auth_headers, db):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    before = db.query(InferenceGateway).one().api_key_encrypted

    response = client.patch(f"{BASE}/{gateway_id}", json={"base_url": "http://localhost:5580/outro"}, headers=auth_headers)

    assert response.status_code == 200 and response.json()["base_url"] == "http://localhost:5580/outro"
    db.expire_all()
    assert db.query(InferenceGateway).one().api_key_encrypted == before


@pytest.mark.parametrize(
    "new_url",
    ["https://localhost:5580/v1", "http://localhost:5581/v1", "http://127.0.0.1:5580/v1", "http://evil.test/v1"],
)
def test_changing_scheme_host_or_port_requires_new_api_key(client, auth_headers, db, new_url):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    before = db.query(InferenceGateway).one().api_key_encrypted

    response = client.patch(f"{BASE}/{gateway_id}", json={"base_url": new_url}, headers=auth_headers)

    assert response.status_code == 422
    db.expire_all()
    assert db.query(InferenceGateway).one().api_key_encrypted == before


def test_changing_only_host_letter_case_is_the_same_origin(client, auth_headers):
    gateway_id = _create_gateway(client, auth_headers, base_url="http://Gateway.Test/v1").json()["id"]

    response = client.patch(f"{BASE}/{gateway_id}", json={"base_url": "http://gateway.test/v1"}, headers=auth_headers)

    assert response.status_code == 200


# --- timeout: padrao 60 s; probe e remote-models em tentativa unica com 15 s ---- #

def test_gateway_timeout_defaults_to_60_seconds(client, auth_headers, db):
    response = _create_gateway(client, auth_headers)

    assert response.json()["timeout_seconds"] == 60
    assert db.query(InferenceGateway).one().timeout_seconds == 60


def test_model_probe_uses_single_attempt_and_15s_timeout(client, auth_headers, mock_gateway):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    model_id = _create_model(client, auth_headers, gateway_id).json()["id"]
    mock_gateway["handler"] = lambda r: httpx.Response(503, text="down")

    body = client.post(f"{BASE}/models/{model_id}/test", headers=auth_headers).json()

    assert body["ok"] is False and "HTTP 503" in body["error"]
    assert len(mock_gateway["requests"]) == 1  # sem retry
    assert mock_gateway["build_kwargs"] == [{"timeout": 15.0, "max_attempts": 1}]


def test_remote_models_uses_single_attempt_and_15s_timeout(client, auth_headers, mock_gateway):
    gateway_id = _create_gateway(client, auth_headers).json()["id"]
    mock_gateway["handler"] = lambda r: httpx.Response(429, text="slow")

    response = client.get(f"{BASE}/{gateway_id}/remote-models", headers=auth_headers)

    assert response.status_code == 502
    assert len(mock_gateway["requests"]) == 1
    assert mock_gateway["build_kwargs"] == [{"timeout": 15.0, "max_attempts": 1}]
