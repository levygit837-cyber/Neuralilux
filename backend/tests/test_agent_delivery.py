import json
import os

import pytest

from app.agents.agent_executor import WhatsAppAgent
from app.services.evolution_api import EvolutionAPIService
from app.services.message_queue_service import MessageQueueService


@pytest.mark.asyncio
async def test_send_response_awaits_evolution_api(monkeypatch):
    captured = {}

    async def fake_send_text_message(self, instance_name, remote_jid, text):
        captured["instance_name"] = instance_name
        captured["remote_jid"] = remote_jid
        captured["text"] = text
        return {"key": {"id": "msg-1"}}

    monkeypatch.setattr(EvolutionAPIService, "send_text_message", fake_send_text_message)

    agent = WhatsAppAgent()

    result = await agent._send_response(
        instance_name="Whatsapp",
        remote_jid="5511999999999@s.whatsapp.net",
        response="Oi, tudo bem?",
    )

    assert result is True
    assert captured == {
        "instance_name": "Whatsapp",
        "remote_jid": "5511999999999@s.whatsapp.net",
        "text": "Oi, tudo bem?",
    }


def test_publish_webhook_event_serializes_bytes_payload():
    published = {}

    class FakeChannel:
        is_closed = False

        def basic_publish(self, exchange, routing_key, body, properties):
            published["exchange"] = exchange
            published["routing_key"] = routing_key
            published["body"] = body
            published["properties"] = properties

    service = MessageQueueService()
    service.channel = FakeChannel()

    result = service.publish_webhook_event(
        {
            "event": "messages.upsert",
            "instance": "Whatsapp",
            "data": {
                "message": {
                    "audioMessage": {
                        "mediaKey": b"\x00\x01\x02",
                    }
                }
            },
        }
    )

    assert result is True
    serialized = json.loads(published["body"])
    assert serialized["event"] == "messages.upsert"
    assert serialized["data"]["data"]["message"]["audioMessage"]["mediaKey"] == "AAEC"


def test_worker_runtime_uses_real_evolution_api_key():
    assert os.environ.get("EVOLUTION_API_KEY") not in {None, "", "change-me-in-production"}
