"""Tests for Messages and Webhooks endpoints."""

import pytest
from fastapi import status


class TestMessagesList:
    def test_list_messages(self, client):
        resp = client.get("/api/v1/messages/")
        assert resp.status_code == 200
        assert "message" in resp.json()


class TestSendMessage:
    def test_send_message(self, client):
        resp = client.post("/api/v1/messages/send")
        assert resp.status_code == 200
        assert "message" in resp.json()


class TestGetMessage:
    def test_get_message(self, client):
        resp = client.get("/api/v1/messages/msg-123")
        assert resp.status_code == 200
        assert "msg-123" in resp.json()["message"]


class TestGetConversation:
    def test_get_conversation(self, client):
        resp = client.get("/api/v1/messages/conversation/5511999999999")
        assert resp.status_code == 200
        assert "5511999999999" in resp.json()["message"]


class TestWebhooks:
    def test_webhook_test_endpoint(self, client):
        resp = client.get("/api/v1/webhooks/evolution/test")
        assert resp.status_code == 200
        assert resp.json()["status"] == "webhook endpoint is accessible"

    def test_webhook_evolution_message(self, client):
        payload = {
            "event": "messages.upsert",
            "instance": "test-instance",
            "data": {
                "key": {"remoteJid": "5511999999999@s.whatsapp.net", "fromMe": False, "id": "msg-1"},
                "message": {"conversation": "Hello"}
            }
        }
        resp = client.post("/api/v1/webhooks/evolution", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "received"
        assert resp.json()["event"] == "messages.upsert"

    def test_webhook_connection_update(self, client):
        payload = {
            "event": "connection.update",
            "instance": "test-instance",
            "data": {"state": "open"}
        }
        resp = client.post("/api/v1/webhooks/evolution", json=payload)
        assert resp.status_code == 200
        assert resp.json()["event"] == "connection.update"
