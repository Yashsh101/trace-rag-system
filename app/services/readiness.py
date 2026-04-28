import uuid

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.types import is_sqlite_url
from app.services.storage import build_storage_backend


def readiness_check(db: Session) -> dict:
    checks = {
        "db": _check_db(db),
        "pgvector": _check_pgvector(db),
        "alembic": _check_alembic(db),
        "storage": _check_storage(),
        "config": _check_config(),
    }
    ready = all(item["ok"] for item in checks.values())
    return {"ready": ready, "checks": checks}


def _check_db(db: Session) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_pgvector(db: Session) -> dict:
    if is_sqlite_url():
        return {"ok": True, "skipped": True, "reason": "sqlite local development mode"}
    try:
        exists = db.execute(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")).scalar()
        return {"ok": bool(exists)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_alembic(db: Session) -> dict:
    try:
        if is_sqlite_url():
            db.execute(text("SELECT 1 FROM documents LIMIT 1"))
            return {"ok": True, "skipped": True, "reason": "sqlite schema initialized from SQLAlchemy metadata"}
        db_revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
        return {"ok": db_revision == head, "current": db_revision, "head": head}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_storage() -> dict:
    try:
        storage = build_storage_backend()
        key = f"health/{uuid.uuid4().hex}.txt"
        uri = storage.put_bytes(key, b"ok", "text/plain")
        content = storage.get_bytes(uri)
        storage.delete(uri)
        return {"ok": content == b"ok", "backend": storage.name}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "backend": settings.storage_backend}


def _check_config() -> dict:
    try:
        if settings.app_env.lower() in {"prod", "production"}:
            # Settings validators have already run; this branch documents that readiness includes config.
            return {"ok": True, "environment": settings.app_env}
        return {"ok": True, "environment": settings.app_env}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
