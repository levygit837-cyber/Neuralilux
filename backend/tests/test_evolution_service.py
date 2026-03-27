"""Unit tests for EvolutionAPIService."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.evolution_api import EvolutionAPIService, EvolutionAPIError


class TestEvolutionAPIError:
    def test_message_and_code(self):
        err = EvolutionAPIError("test error", 400)
        assert err.message == "test error"
        assert err.status_code == 400
        assert str(err) == "test error"

    def test_default_status_code(self):
        err = EvolutionAPIError("server error")
        assert err.status_code == 500


class TestEvolutionAPIService:
    def test_init_sets_base_url_and_headers(self):
        svc = EvolutionAPIService()
        assert svc.base_url is not None
        assert "apikey" in svc.headers
        assert "Content-Type" in svc.headers
