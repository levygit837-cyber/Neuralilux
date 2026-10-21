"""Tests for Messages endpoints. O webhook da Evolution é coberto em test_webhook_auth.py."""

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
