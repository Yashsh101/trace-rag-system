from datetime import datetime
from typing import Any

from sqlalchemy import Computed, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import embedding_type, is_sqlite_url, search_vector_type

_SEARCH_VECTOR_ARGS = () if is_sqlite_url() else (Computed("to_tsvector('english', coalesce(text, ''))", persisted=True),)


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_version_id", "chunk_index", name="uq_version_chunk_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    document_version_id: Mapped[int] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    search_vector: Mapped[str | None] = mapped_column(
        search_vector_type(),
        *_SEARCH_VECTOR_ARGS,
        nullable=True,
    )
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    embedding: Mapped[list[float]] = mapped_column(embedding_type(), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="chunks")
    document_version: Mapped["DocumentVersion"] = relationship(back_populates="chunks")
