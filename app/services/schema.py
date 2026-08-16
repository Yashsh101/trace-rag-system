"""SQLite/local schema initialization.

Postgres deployments use Alembic migrations (``alembic upgrade head``).
For the local/demo mode the SQLite database is initialized directly from the
SQLAlchemy model metadata so the console works out of the box without a
migration toolchain. This module is a no-op on Postgres connections.
"""

import logging

from app.core.config import settings
from app.db.base import Base
from app.db.types import is_sqlite_url

logger = logging.getLogger(__name__)


def initialize_sqlite_schema() -> None:
    """Create all tables when running against a SQLite database.

    Safe to call repeatedly: ``create_all`` skips tables that already exist.
    Non-SQLite connections are left to Alembic migrations.
    """
    if not is_sqlite_url():
        return
    from app.db.session import engine
    from app import models  # noqa: F401 - register all models with metadata

    Base.metadata.create_all(engine)
    logger.info("sqlite_schema_initialized")
