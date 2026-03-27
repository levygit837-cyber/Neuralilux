"""
Conftest for inference tests - bypasses database setup.
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends
from unittest.mock import patch, MagicMock

from app.api.v1.endpoints.messages import router as messages_router
from app.api.v1.endpoints.auth import get_current_user


# Create a minimal FastAPI app for testing
app = FastAPI()
app.include_router(messages_router, prefix="/api/v1/messages")


# Mock user for authentication
MOCK_USER = MagicMock()
MOCK_USER.id = "test-user-id"
MOCK_USER.email = "test@example.com"
MOCK_USER.is_superuser = False


# Override get_current_user dependency
async def override_get_current_user():
    return MOCK_USER


app.dependency_overrides[get_current_user] = override_get_current_user


@pytest.fixture
def client():
    """Create test client without database."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Get mock authentication headers."""
    return {"Authorization": "Bearer test-token"}
