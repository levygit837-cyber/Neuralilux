"""O socket realtime da Evolution não perde o evento calado: a falha de publish loga o evento e o id da Message."""
import pytest
import structlog

from app.whatsapp.evolution_realtime import EvolutionRealtimeService


@pytest.mark.asyncio
async def test_failed_publish_is_logged_with_event_and_message_id(monkeypatch):
    async def broker_down(_payload):
        return False

    monkeypatch.setattr("app.whatsapp.evolution_realtime.message_queue_service.publish_webhook_event", broker_down)
    payload = {"instance": "evo-rt", "data": {"key": {"id": "msg-perdida"}}}

    with structlog.testing.capture_logs() as logs:
        await EvolutionRealtimeService()._forward_event("messages.upsert", payload)

    lost = [log for log in logs if log["event"].startswith("Evolution realtime event lost")]
    assert [(log["event_type"], log["message_ids"]) for log in lost] == [("messages.upsert", ["msg-perdida"])]
