import os
import tempfile

# Arquivo SQLite próprio deste processo: duas suítes rodando juntas (worktrees diferentes, ou xdist) não
# dividem o mesmo arquivo nem derrubam as tabelas uma da outra. Fica fora do repositório.
TEST_DB_PATH = os.path.join(tempfile.gettempdir(), f"neuralilux-test-{os.getpid()}.db")
if os.path.exists(TEST_DB_PATH):  # sobra de uma execução morta cujo pid foi reaproveitado
    os.remove(TEST_DB_PATH)

# Isola a suíte do banco de desenvolvimento: tem que vir antes de qualquer import de `app`,
# porque app.core.database cria o engine com settings.DATABASE_URL na importação.
# Com RUN_E2E=1 a suíte usa o banco configurado no ambiente (testes e2e criam dados reais).
if os.environ.get("RUN_E2E") != "1":
    os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

# Sem ENVIRONMENT=development explícito a app recusa segredos de exemplo (e a CI não tem segredos): a suíte
# declara o modo de desenvolvimento aqui, antes de qualquer import de `app`.
os.environ["ENVIRONMENT"] = "development"

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
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
from app.api.deps import get_db
from app.core.database import Base
from app.core import security

# Custo mínimo do bcrypt (4) só nos testes: cada usuário de teste registra e faz login,
# e com o custo de produção (12) isso somava ~0,6 s por hash. Produção segue em 12.
security.BCRYPT_ROUNDS = 4

# Test database (o mesmo arquivo do `DATABASE_URL` forçado acima)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


# Custom markers
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests with real dependencies"
    )
    config.addinivalue_line(
        "markers", "postgres: precisa de um Postgres de teste (variável TEST_POSTGRES_URL); sem ela o teste é pulado"
    )
    config.addinivalue_line(
        "markers", "rabbitmq: precisa de um RabbitMQ de teste (variável TEST_RABBITMQ_URL); sem ela o teste é pulado"
    )


def pytest_collection_modifyitems(config, items):
    """`e2e` fala com serviços reais (LLM, Evolution, banco de dev): só roda com RUN_E2E=1.

    `postgres` precisa de um servidor Postgres de teste: só roda com `TEST_POSTGRES_URL` definida.
    `rabbitmq` precisa de um RabbitMQ de teste: só roda com `TEST_RABBITMQ_URL` definida.
    """
    skip_e2e = pytest.mark.skip(reason="teste e2e: defina RUN_E2E=1 para rodar contra serviços reais")
    skip_postgres = pytest.mark.skip(reason="teste postgres: defina TEST_POSTGRES_URL (veja AGENTS.md)")
    skip_rabbitmq = pytest.mark.skip(reason="teste rabbitmq: defina TEST_RABBITMQ_URL (veja AGENTS.md)")
    for item in items:
        if "e2e" in item.keywords and os.environ.get("RUN_E2E") != "1":
            item.add_marker(skip_e2e)
        if "postgres" in item.keywords and not os.environ.get("TEST_POSTGRES_URL"):
            item.add_marker(skip_postgres)
        if "rabbitmq" in item.keywords and not os.environ.get("TEST_RABBITMQ_URL"):
            item.add_marker(skip_rabbitmq)


@pytest.fixture
def db():
    """Create test database"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Populate delivery zones for testing
    from app.models import DeliveryZone
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
def db_session():
    """Sessão em SQLite em memória, isolada do `db` (que usa o arquivo SQLite do processo)."""
    memory_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    MemorySession = sessionmaker(autocommit=False, autoflush=False, bind=memory_engine)
    Base.metadata.create_all(bind=memory_engine)

    session = MemorySession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=memory_engine)


@pytest.fixture
def conversation_factory(db):
    """Cria Instance + Contact + Conversation reais com o id pedido.

    Os testes do Agent e dos Packs precisam de linhas reais por causa das chaves estrangeiras.
    """
    from app.models import Contact, Conversation, Instance

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
def fake_rate_limit_redis(monkeypatch):
    """Rate limit contra um Redis em memória por teste, e cadastro público aberto (o padrão de produção é fechado).

    Sem isto os testes falariam fechado (503) por não achar Redis, e os contadores vazariam de um teste
    para outro. Testes do próprio limite ajustam `settings` ou trocam o cliente por um que falha.
    """
    import fakeredis

    from app.core import rate_limit
    from app.core.config import settings

    server = fakeredis.FakeServer()
    monkeypatch.setattr(
        rate_limit, "_new_client", lambda: fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    )
    monkeypatch.setattr(rate_limit, "_redis", None)
    monkeypatch.setattr(rate_limit, "_redis_loop", None)
    monkeypatch.setattr(settings, "ALLOW_PUBLIC_REGISTRATION", True)
    # Folga larga: a suíte registra e loga dezenas de usuários pelo mesmo IP de teste.
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ATTEMPTS", 10_000)
    monkeypatch.setattr(settings, "REGISTER_RATE_LIMIT_ATTEMPTS", 10_000)
    yield server


@pytest.fixture(autouse=True)
def _no_real_realtime_publish(monkeypatch):
    """Impede que os testes publiquem no Redis real via realtime_event_bus.

    O singleton guarda um cliente Redis preso ao event loop do primeiro teste async;
    nos seguintes ele falha com "Event loop is closed". Testes que querem observar
    eventos continuam podendo sobrescrever `publish` com monkeypatch/patch.
    """
    from app.realtime.event_bus import realtime_event_bus

    monkeypatch.setattr(realtime_event_bus, "publish", AsyncMock())


@pytest.fixture(autouse=True)
def _isolated_gateway_registry(monkeypatch):
    """Nenhum teste enxerga gateways do banco de dev.

    Modulos soltos importados antes deste conftest podem ligar `app.core.database.SessionLocal`
    ao Postgres de desenvolvimento (onde o gateway Kiro-backend e semeado). O registry le
    `SessionLocal` em tempo de chamada, entao apontamos para o SQLite de teste e limpamos o cache.
    """
    from app.core import database
    from app.llm import registry as gateway_registry

    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)
    gateway_registry.invalidate()
    yield
    gateway_registry.invalidate()
