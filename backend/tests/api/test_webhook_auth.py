"""O webhook da Evolution só aceita chamadas com `?token=` igual a EVOLUTION_WEBHOOK_TOKEN (ADR 0006)."""
import pytest

from app.core.config import Settings, settings

TOKEN = "t0ken-de-teste-com-entropia-suficiente"
PAYLOAD = {"event": "messages.upsert", "instance": "evo-auth", "data": {"key": {"id": "m1"}}}


@pytest.fixture
def published(monkeypatch):
    """Configura o token e captura o que seria publicado no RabbitMQ."""
    events = []

    async def fake_publish(event):
        events.append(event)
        return True

    monkeypatch.setattr(settings, "EVOLUTION_WEBHOOK_TOKEN", TOKEN)
    monkeypatch.setattr("app.api.routes.webhooks.message_queue_service.publish_webhook_event", fake_publish)
    return events


@pytest.mark.parametrize("path", ["/api/v1/webhooks/evolution", "/api/v1/webhooks/evolution/messages-upsert"])
def test_post_without_token_is_unauthorized_and_not_published(client, published, path):
    response = client.post(path, json=PAYLOAD)

    assert response.status_code == 401
    assert published == []


@pytest.mark.parametrize("token", ["", "errado", TOKEN + "x", TOKEN[:-1]])
def test_post_with_wrong_token_is_unauthorized(client, published, token):
    response = client.post("/api/v1/webhooks/evolution", params={"token": token}, json=PAYLOAD)

    assert response.status_code == 401
    assert published == []


def test_post_with_non_ascii_token_is_unauthorized_not_a_server_error(client, published):
    response = client.post("/api/v1/webhooks/evolution", params={"token": "tokén"}, json=PAYLOAD)

    assert response.status_code == 401


def test_post_with_correct_token_is_published(client, published):
    response = client.post("/api/v1/webhooks/evolution", params={"token": TOKEN}, json=PAYLOAD)

    assert response.status_code == 200
    assert [event["event"] for event in published] == ["messages.upsert"]


def test_event_path_with_correct_token_is_published(client, published):
    response = client.post(
        "/api/v1/webhooks/evolution/connection-update", params={"token": TOKEN}, json={"instance": "evo-auth"}
    )

    assert response.status_code == 200
    assert published[0]["event"] == "connection.update"


# Com WEBHOOK_BY_EVENTS=true a Evolution faz POST em `<url>?token=X/messages-upsert`: o path continua
# `/evolution` e o evento chega colado ao valor do token.
def test_event_suffix_glued_to_the_token_is_accepted_and_used_as_event(client, published):
    response = client.post(
        "/api/v1/webhooks/evolution", params={"token": f"{TOKEN}/connection-update"}, json={"instance": "evo-auth"}
    )

    assert response.status_code == 200
    assert published[0]["event"] == "connection.update"


def test_payload_event_wins_over_the_suffix_glued_to_the_token(client, published):
    response = client.post("/api/v1/webhooks/evolution", params={"token": f"{TOKEN}/qrcode-updated"}, json=PAYLOAD)

    assert response.status_code == 200
    assert published[0]["event"] == "messages.upsert"


@pytest.mark.parametrize("token", ["errado/messages-upsert", f"{TOKEN}x/messages-upsert", "/messages-upsert"])
def test_suffix_does_not_rescue_a_wrong_secret(client, published, token):
    response = client.post("/api/v1/webhooks/evolution", params={"token": token}, json=PAYLOAD)

    assert response.status_code == 401
    assert published == []


def test_token_followed_by_a_bare_slash_is_accepted_without_event(client, published):
    response = client.post("/api/v1/webhooks/evolution", params={"token": f"{TOKEN}/"}, json={"instance": "evo-auth"})

    assert response.status_code == 200
    assert published[0].get("event") is None


def test_unconfigured_token_rejects_every_call_even_with_an_empty_token(client, published, monkeypatch):
    monkeypatch.setattr(settings, "EVOLUTION_WEBHOOK_TOKEN", "")

    assert client.post("/api/v1/webhooks/evolution", json=PAYLOAD).status_code == 401
    assert client.post("/api/v1/webhooks/evolution", params={"token": ""}, json=PAYLOAD).status_code == 401
    assert published == []


def test_health_probe_also_requires_the_token(client, published):
    assert client.get("/api/v1/webhooks/evolution/test").status_code == 401
    assert client.get("/api/v1/webhooks/evolution/test", params={"token": TOKEN}).status_code == 200


def test_settings_do_not_ship_secrets_or_debug_on_by_default():
    defaults = Settings(_env_file=None)

    assert defaults.DEBUG is False
    assert defaults.EVOLUTION_API_KEY == ""
    assert defaults.EVOLUTION_WEBHOOK_TOKEN == ""
