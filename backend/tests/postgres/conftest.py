"""Fixtures dos testes que precisam de Postgres de verdade (marcador `postgres`).

A variável `TEST_POSTGRES_URL` aponta para um *servidor* (usuário com CREATEDB); nunca é lida a `DATABASE_URL`.
Os testes não escrevem no banco da URL: cada processo cria um banco descartável `nlx_pgtest_<id>`, migra com o
Alembic e o apaga no fim. Assim, mesmo apontada por engano para o banco de dev, a URL só vê um CREATE/DROP de um
banco com nome aleatório.
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _driver_url(url: str) -> URL:
    """A mesma URL com o driver psycopg 3, que é o que a aplicação usa."""
    return make_url(url).set(drivername="postgresql+psycopg")


@pytest.fixture(scope="session")
def server_url() -> URL:
    return _driver_url(os.environ["TEST_POSTGRES_URL"])


@pytest.fixture(scope="session")
def make_database(server_url):
    """Fábrica de bancos vazios e descartáveis no servidor de teste; todos são apagados no fim da sessão."""
    created: list[str] = []
    admin = create_engine(server_url, isolation_level="AUTOCOMMIT")

    def _make() -> URL:
        name = f"nlx_pgtest_{uuid.uuid4().hex[:12]}"
        with admin.connect() as conn:
            conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
        created.append(name)
        return server_url.set(database=name)

    yield _make

    with admin.connect() as conn:
        for name in created:
            conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    admin.dispose()


def run_alembic(url: URL, *args: str) -> None:
    """Roda `alembic <args>` contra `url`, como o CI e o deploy fazem (o `env.py` lê `DATABASE_URL`)."""
    env = {**os.environ, "DATABASE_URL": url.render_as_string(hide_password=False)}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"alembic {' '.join(args)} falhou:\n{result.stdout}\n{result.stderr}"


@pytest.fixture(scope="session")
def migrated_engine(make_database):
    """Engine de um banco criado só pelas migrações (`alembic upgrade head`), nunca por `create_all`."""
    url = make_database()
    run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def pg(migrated_engine):
    """Sessão no schema migrado; tudo que o teste grava é desfeito no fim (commit vira SAVEPOINT)."""
    connection = migrated_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", autoflush=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
