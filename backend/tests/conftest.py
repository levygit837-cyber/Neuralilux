import os

# Isola a suíte do banco de desenvolvimento: tem que vir antes de qualquer import de `app`,
# porque app.core.database cria o engine com settings.DATABASE_URL na importação.
# Com RUN_E2E=1 a suíte usa o banco configurado no ambiente (testes e2e criam dados reais).
if os.environ.get("RUN_E2E") != "1":
    os.environ["DATABASE_URL"] = "sqlite:///./test.db"

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


# Custom marker for E2E tests
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests with real dependencies"
    )


def pytest_collection_modifyitems(config, items):
    """Testes `e2e` falam com serviços reais (LLM, Evolution, banco de dev): só rodam com RUN_E2E=1."""
    if os.environ.get("RUN_E2E") == "1":
        return
    skip_e2e = pytest.mark.skip(reason="teste e2e: defina RUN_E2E=1 para rodar contra serviços reais")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)


@pytest.fixture
def db():
    """Create test database"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Populate delivery zones for testing
    from app.models.models import DeliveryZone
    zone1 = DeliveryZone(
        id="zone_test_001",
        name="Centro",
        neighborhoods=["Centro", "Centro Histórico"],
        delivery_fee=5.00,
        minimum_order_value=30.00,
        is_active=True
    )
    zone2 = DeliveryZone(
        id="zone_test_002",
        name="Zona Norte",
        neighborhoods=["Vila Nova", "Jardim das Flores"],
        delivery_fee=8.00,
        minimum_order_value=30.00,
        is_active=True
    )
    db.add(zone1)
    db.add(zone2)
    db.commit()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def conversation_factory(db):
    """Cria Instance + Contact + Conversation reais com o id pedido.

    order_service valida a existência da Conversation antes de abrir a comanda.
    """
    from app.models.models import Contact, Conversation, Instance

    def _make(conversation_id: str, remote_jid: str = "5511999999999@s.whatsapp.net") -> Conversation:
        instance = Instance(name=f"inst-{conversation_id}", evolution_instance_id=f"evo-{conversation_id}")
        db.add(instance)
        db.flush()
        contact = Contact(
            instance_id=instance.id,
            phone_number=remote_jid.split("@")[0],
            remote_jid=remote_jid,
            name="Cliente Teste",
        )
        db.add(contact)
        db.flush()
        conversation = Conversation(
            id=conversation_id,
            instance_id=instance.id,
            contact_id=contact.id,
            remote_jid=remote_jid,
        )
        db.add(conversation)
        db.commit()
        return conversation

    return _make



@pytest.fixture
def client(db):
    """Create test client"""
    def override_get_db():
        # Não fecha `db`: a sessão é compartilhada com o teste, que ainda usa os objetos
        # depois da request. Quem fecha é o fixture `db`.
        yield db

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


@pytest.fixture(autouse=True)
def _no_real_realtime_publish(monkeypatch):
    """Impede que os testes publiquem no Redis real via realtime_event_bus.

    O singleton guarda um cliente Redis preso ao event loop do primeiro teste async;
    nos seguintes ele falha com "Event loop is closed". Testes que querem observar
    eventos continuam podendo sobrescrever `publish` com monkeypatch/patch.
    """
    from app.services.realtime_event_bus import realtime_event_bus

    monkeypatch.setattr(realtime_event_bus, "publish", AsyncMock())


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

