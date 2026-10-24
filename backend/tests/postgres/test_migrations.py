"""Migrações do Alembic no Postgres: ida, volta, ida de novo, e models iguais ao schema migrado."""
import pytest
from sqlalchemy import Column, Integer, MetaData, create_engine, inspect

from app.core.database import Base
from tests.postgres.alembic_runner import run_alembic
from tests.postgres.schema_drift import schema_diff

pytestmark = pytest.mark.postgres


def _tables(engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_upgrade_downgrade_upgrade_from_an_empty_database(make_database):
    url = make_database()
    engine = create_engine(url)
    try:
        run_alembic(url, "upgrade", "head")
        migrated = _tables(engine)
        assert migrated, "upgrade head não criou nenhuma tabela"

        run_alembic(url, "downgrade", "base")
        assert _tables(engine) == set()

        run_alembic(url, "upgrade", "head")
        assert _tables(engine) == migrated
    finally:
        engine.dispose()


def test_models_match_the_migrated_schema(migrated_engine):
    with migrated_engine.connect() as connection:
        diff = schema_diff(connection, Base.metadata)

    assert diff == [], (
        "Os models divergem do schema migrado. Crie a migração (ou corrija o model):\n  " + "\n  ".join(diff)
    )


def test_comparator_reports_a_model_changed_without_migration(migrated_engine):
    changed = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(changed)
    changed.tables["contacts"].append_column(Column("coluna_sem_migracao", Integer))
    changed.remove(changed.tables["tickets"])

    with migrated_engine.connect() as connection:
        diff = schema_diff(connection, changed)

    assert "add_column: contacts.coluna_sem_migracao" in diff
    assert "remove_table: tickets" in diff
