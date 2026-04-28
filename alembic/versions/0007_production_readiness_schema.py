"""production readiness schema

Revision ID: 0007_production_readiness_schema
Revises: 0006_add_auth_acl
Create Date: 2026-04-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_production_readiness_schema"
down_revision: Union[str, None] = "0006_add_auth_acl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("ingestion_jobs", "content")
    op.add_column("ingestion_jobs", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ingestion_jobs", sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("ingestion_jobs", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("locked_by", sa.String(length=128), nullable=True))
    op.create_unique_constraint("uq_document_content_owner", "documents", ["content_hash", "owner_id"])
    op.execute(
        """
        ALTER TABLE chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED
        """
    )
    op.create_index("ix_chunks_search_vector_gin", "chunks", ["search_vector"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_chunks_search_vector_gin", table_name="chunks", postgresql_using="gin")
    op.drop_column("chunks", "search_vector")
    op.drop_constraint("uq_document_content_owner", "documents", type_="unique")
    op.drop_column("ingestion_jobs", "locked_by")
    op.drop_column("ingestion_jobs", "locked_at")
    op.drop_column("ingestion_jobs", "last_attempt_at")
    op.drop_column("ingestion_jobs", "max_retries")
    op.drop_column("ingestion_jobs", "retry_count")
    op.add_column("ingestion_jobs", sa.Column("content", sa.LargeBinary(), nullable=True))

