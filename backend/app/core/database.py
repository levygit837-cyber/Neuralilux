from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


database_url = settings.DATABASE_URL

if database_url.startswith("sqlite"):
    engine_kwargs = {
        "connect_args": {"check_same_thread": False},
        "pool_pre_ping": True,
    }
    if database_url in {"sqlite://", "sqlite:///:memory:"}:
        engine_kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, **engine_kwargs)
else:
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def commit_or_rollback(db: Session) -> None:
    """`db.commit()`; se falhar, `rollback` e relança. A Session segue utilizável (Socket.IO e worker não a fecham por request)."""
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
