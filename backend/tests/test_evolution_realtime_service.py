import pytest


@pytest.mark.asyncio
async def test_forward_event_publishes_webhook_payload(monkeypatch):
    published_payloads = []

    def fake_publish(payload):
        published_payloads.append(payload)
        return True

    monkeypatch.setattr(
        "app.services.evolution_realtime.message_queue_service.publish_webhook_event",
        fake_publish,
    )

    from app.services.evolution_realtime import EvolutionRealtimeService

    service = EvolutionRealtimeService()
    payload = {
        "instance": "evo-realtime-1",
        "data": {
            "key": {
                "id": "msg-1",
            }
        },
    }

    await service._forward_event("messages.upsert", payload)

    assert published_payloads == [
        {
            "event": "messages.upsert",
            "instance": "evo-realtime-1",
            "data": {
                "key": {
                    "id": "msg-1",
                }
            },
            "source": "websocket",
        }
    ]
