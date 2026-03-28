import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON

# Monkey-patch JSONB to JSON for SQLite compatibility in tests
# This allows models using JSONB to work with SQLite during testing
import sqlalchemy.dialects.sqlite
if not hasattr(sqlalchemy.dialects.sqlite.base.SQLiteTypeCompiler, 'visit_JSONB'):
    sqlalchemy.dialects.sqlite.base.SQLiteTypeCompiler.visit_JSONB = (
        sqlalchemy.dialects.sqlite.base.SQLiteTypeCompiler.visit_JSON
    )

from app.main import app
from app.core.database import Base, get_db

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """Create test database"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db):
    """Create test client"""
    def override_get_db():
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Get authentication headers"""
    # Create test user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "testpass123",
            "full_name": "Test User"
        }
    )

    # Login
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "test@example.com",
            "password": "testpass123"
        }
    )

    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_realtime_event_bus():
    """Mock realtime event bus for testing"""
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    return mock_bus


@pytest.fixture
def mock_inference_service():
    """Mock inference service for testing"""
    mock_service = MagicMock()
    mock_service.astream_chat_completion_with_thinking = AsyncMock()
    mock_service.chat_completion = AsyncMock()
    return mock_service


@pytest.fixture
def mock_super_realtime_event_bus():
    """Mock super agent realtime event bus for testing"""
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    return mock_bus


@pytest.fixture
def mock_super_inference_service():
    """Mock super agent inference service for testing"""
    mock_service = MagicMock()
    mock_service.astream_chat_completion_with_thinking = AsyncMock()
    mock_service.chat_completion = AsyncMock()
    return mock_service

