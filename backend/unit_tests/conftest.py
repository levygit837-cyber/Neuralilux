import os

import sqlalchemy.dialects.sqlite
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.core.database import Base


if not hasattr(sqlalchemy.dialects.sqlite.base.SQLiteTypeCompiler, "visit_JSONB"):
    sqlalchemy.dialects.sqlite.base.SQLiteTypeCompiler.visit_JSONB = (
        sqlalchemy.dialects.sqlite.base.SQLiteTypeCompiler.visit_JSON
    )


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
