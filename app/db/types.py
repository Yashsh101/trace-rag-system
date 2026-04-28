from sqlalchemy import JSON, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

from app.core.config import settings


def is_sqlite_url(database_url: str | None = None) -> bool:
    return (database_url or settings.database_url).startswith("sqlite")


def json_document_type():
    return JSON() if is_sqlite_url() else JSONB()


def search_vector_type():
    return Text() if is_sqlite_url() else TSVECTOR()


def embedding_type():
    if is_sqlite_url():
        return JSON()

    from pgvector.sqlalchemy import Vector

    return Vector(settings.embedding_dimension)
