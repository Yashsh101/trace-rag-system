from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.types import is_sqlite_url

engine_kwargs = {"pool_pre_ping": True}
if is_sqlite_url():
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Prevent import-time hangs when Postgres is unreachable (tests/imports only need engine creation)
    engine_kwargs["connect_args"] = {"connect_timeout": 3}

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
