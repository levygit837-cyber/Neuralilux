"""Tests for WhatsApp endpoints (QR Code, Status, Disconnect)."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import status


@pytest.fixture
def mock_qr_response():
    return {"qrcode": {"base64": "data:image/png;base64,test"}, "code": "2@test"}


@pytest.fixture
def mock_status_open():
    return {"instance": {"instanceName": "test", "state": "open"}}


@pytest.fixture
def mock_status_close():
    return {"instance": {"instanceName": "test", "state": "close"}}


@pytest.fixture
def disconnected_instance(db, auth_headers, client):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = resp.json()["id"]
    from app.models.models import Instance
    inst = Instance(id="inst-d-001", name="Disc", phone_number="5511999999999",
                    evolution_instance_id="evo-d-001", status="disconnected",
                    is_active=True, owner_id=user_id)
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


@pytest.fixture
def connected_instance(db, auth_headers, client):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = resp.json()["id"]
    from app.models.models import Instance
    inst = Instance(id="inst-c-002", name="Conn", phone_number="5511888888888",
                    evolution_instance_id="evo-c-002", status="connected",
                    is_active=True, owner_id=user_id)
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


# ============== QR Code Tests ==============

class TestGetQRCode:

    @patch("app.api.v1.endpoints.whatsapp.evolution_api")
    def test_success(self, mock_evo, client, auth_headers, disconnected_instance, mock_qr_response):
        mock_evo.get_instance_qrcode = AsyncMock(return_value=mock_qr_response)
        resp = client.get("/api/v1/whatsapp/qr", params={"instance_id": "inst-d-001"}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["qr_code"] is not None
        assert data["status"] == "connecting"

    @patch("app.api.v1.endpoints.whatsapp.evolution_api")
    def test_already_connected(self, mock_evo, client, auth_headers, connected_instance, mock_status_open):
        mock_evo.get_instance_qrcode = AsyncMock(return_value={})
        mock_evo.get_instance_status = AsyncMock(return_value=mock_status_open)
        resp = client.get("/api/v1/whatsapp/qr", params={"instance_id": "inst-c-002"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["qr_code"] is None

    def test_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/whatsapp/qr", params={"instance_id": "nope"}, headers=auth_headers)
        assert resp.status_code == 404

    def test_unauthorized(self, client, disconnected_instance):
        resp = client.get("/api/v1/whatsapp/qr", params={"instance_id": "inst-d-001"})
        assert resp.status_code == 401

    @patch("app.api.v1.endpoints.whatsapp.evolution_api")
    def test_evolution_error(self, mock_evo, client, auth_headers, disconnected_instance):
        async def raise_err(*a, **kw):
            from app.services.evolution_api import EvolutionAPIError
            raise EvolutionAPIError("fail", 500)
        mock_evo.get_instance_qrcode = raise_err
        resp = client.get("/api/v1/whatsapp/qr", params={"instance_id": "inst-d-001"}, headers=auth_headers)
        assert resp.status_code == 502


# ============== Status Tests ==============

class TestGetStatus:

    @patch("app.api.v1.endpoints.whatsapp.evolution_api")
    def test_connected(self, mock_evo, client, auth_headers, connected_instance, mock_status_open):
        mock_evo.get_instance_status = AsyncMock(return_value=mock_status_open)
        resp = client.get("/api/v1/whatsapp/status", params={"instance_id": "inst-c-002"}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "connected"
        assert data["evolution_state"] == "open"
        assert data["instance_name"] == "Conn"

    @patch("app.api.v1.endpoints.whatsapp.evolution_api")
    def test_disconnected(self, mock_evo, client, auth_headers, disconnected_instance, mock_status_close):
        mock_evo.get_instance_status = AsyncMock(return_value=mock_status_close)
        resp = client.get("/api/v1/whatsapp/status", params={"instance_id": "inst-d-001"}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disconnected"
        assert data["evolution_state"] == "close"

    def test_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/whatsapp/status", params={"instance_id": "nope"}, headers=auth_headers)
        assert resp.status_code == 404

    @patch("app.api.v1.endpoints.whatsapp.evolution_api")
    def test_evolution_error(self, mock_evo, client, auth_headers, disconnected_instance):
        async def raise_err(*a, **kw):
            from app.services.evolution_api import EvolutionAPIError
            raise EvolutionAPIError("timeout", 500)
        mock_evo.get_instance_status = raise_err
        resp = client.get("/api/v1/whatsapp/status", params={"instance_id": "inst-d-001"}, headers=auth_headers)
        assert resp.status_code == 502


# ============== Disconnect Tests ==============

class TestDisconnect:

    @patch("app.api.v1.endpoints.whatsapp.evolution_api")
    def test_success(self, mock_evo, client, auth_headers, connected_instance):
        mock_evo.disconnect_instance = AsyncMock(return_value={"status": "SUCCESS"})
        resp = client.post("/api/v1/whatsapp/disconnect", params={"instance_id": "inst-c-002"}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disconnected"
        assert "disconnected successfully" in data["message"].lower()
        mock_evo.disconnect_instance.assert_called_once_with("evo-c-002")

    def test_already_disconnected(self, client, auth_headers, disconnected_instance):
        resp = client.post("/api/v1/whatsapp/disconnect", params={"instance_id": "inst-d-001"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "disconnected"
        assert "already disconnected" in resp.json()["message"].lower()

    def test_not_found(self, client, auth_headers):
        resp = client.post("/api/v1/whatsapp/disconnect", params={"instance_id": "nope"}, headers=auth_headers)
        assert resp.status_code == 404

    @patch("app.api.v1.endpoints.whatsapp.evolution_api")
    def test_evolution_error(self, mock_evo, client, auth_headers, connected_instance):
        async def raise_err(*a, **kw):
            from app.services.evolution_api import EvolutionAPIError
            raise EvolutionAPIError("fail", 500)
        mock_evo.disconnect_instance = raise_err
        resp = client.post("/api/v1/whatsapp/disconnect", params={"instance_id": "inst-c-002"}, headers=auth_headers)
        assert resp.status_code == 502
