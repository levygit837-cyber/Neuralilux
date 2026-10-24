"""Publicação que falha não pode virar 200: sem 503 a Evolution acha que entregou e a Message some sem rastro."""
import pytest
import structlog

from app.core.config import settings

TOKEN = "t0ken-de-teste-com-entropia-suficiente"
PAYLOAD = {"event": "messages.upsert", "instance": "evo-503", "data": {"key": {"id": "msg-perdida"}}}


@pytest.fixture
def broker(monkeypatch):
    """RabbitMQ de mentira: `accepts` decide se o publish dá certo."""
    state = {"accepts": True, "events": []}

    async def fake_publish(event):
        state["events"].append(event)
        return state["accepts"]

    monkeypatch.setattr(settings, "EVOLUTION_WEBHOOK_TOKEN", TOKEN)
    monkeypatch.setattr("app.api.routes.webhooks.message_queue_service.publish_webhook_event", fake_publish)
    return state


def test_publish_ok_answers_200(client, broker):
    response = client.post("/api/v1/webhooks/evolution", params={"token": TOKEN}, json=PAYLOAD)

    assert response.status_code == 200
    assert response.json() == {"status": "received", "event": "messages.upsert"}


def test_publish_failure_answers_503_and_logs_event_and_message_id(client, broker):
    broker["accepts"] = False

    with structlog.testing.capture_logs() as logs:
        response = client.post("/api/v1/webhooks/evolution", params={"token": TOKEN}, json=PAYLOAD)

    assert response.status_code == 503
    lost = [log for log in logs if log["event"].startswith("Evolution webhook event lost")]
    assert len(lost) == 1
    assert lost[0]["event_type"] == "messages.upsert"
    assert lost[0]["message_ids"] == ["msg-perdida"]
