"""add artifact metadata

Revision ID: 0005_add_artifact_metadata
Revises: 0004_add_ingestion_jobs
Create Date: 2026-04-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_add_artifact_metadata"
down_revision: Union[str, None] = "0004_add_ingestion_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("raw_file_uri", sa.String(length=2048), nullable=True))
    op.add_column("documents", sa.Column("storage_backend", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("file_size_bytes", sa.Integer(), nullable=True))
    op.add_column("document_versions", sa.Column("parsed_text_uri", sa.String(length=2048), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("raw_file_uri", sa.String(length=2048), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("parsed_text_uri", sa.String(length=2048), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("storage_backend", sa.String(length=64), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("file_size_bytes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("ingestion_jobs", "file_size_bytes")
    op.drop_column("ingestion_jobs", "content_hash")
    op.drop_column("ingestion_jobs", "storage_backend")
    op.drop_column("ingestion_jobs", "parsed_text_uri")
    op.drop_column("ingestion_jobs", "raw_file_uri")
    op.drop_column("document_versions", "parsed_text_uri")
    op.drop_column("documents", "file_size_bytes")
    op.drop_column("documents", "storage_backend")
    op.drop_column("documents", "raw_file_uri")

