from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine
from app.db.types import is_sqlite_url
from app.models import citation, chunk, document, query_log  # noqa: F401


def main() -> None:
    if not is_sqlite_url(str(engine.url)):
        raise SystemExit("Local DB init is only for sqlite. Use `alembic upgrade head` for Postgres.")

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
        current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if current is None:
            connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('sqlite_local_schema')"))
    print(f"Initialized SQLite database at {engine.url.database}")


if __name__ == "__main__":
    main()
