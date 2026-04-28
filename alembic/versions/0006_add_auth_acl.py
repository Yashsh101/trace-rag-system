"""add auth and acl metadata

Revision ID: 0006_add_auth_acl
Revises: 0005_add_artifact_metadata
Create Date: 2026-04-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_add_auth_acl"
down_revision: Union[str, None] = "0005_add_artifact_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("owner_id", sa.String(length=128), nullable=True))
    op.add_column("documents", sa.Column("visibility", sa.String(length=32), nullable=False, server_default="private"))
    op.add_column("documents", sa.Column("allowed_user_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("documents", sa.Column("allowed_group_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))

    op.add_column("ingestion_jobs", sa.Column("owner_id", sa.String(length=128), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("visibility", sa.String(length=32), nullable=False, server_default="private"))
    op.add_column("ingestion_jobs", sa.Column("allowed_user_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("ingestion_jobs", sa.Column("allowed_group_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))

    op.add_column("query_logs", sa.Column("user_id", sa.String(length=128), nullable=True))
    op.add_column("query_logs", sa.Column("groups", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")))
    op.add_column("query_logs", sa.Column("auth_role", sa.String(length=32), nullable=True))
    op.add_column("query_logs", sa.Column("denied_retrieval_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("query_logs", "denied_retrieval_count")
    op.drop_column("query_logs", "auth_role")
    op.drop_column("query_logs", "groups")
    op.drop_column("query_logs", "user_id")
    op.drop_column("ingestion_jobs", "allowed_group_ids")
    op.drop_column("ingestion_jobs", "allowed_user_ids")
    op.drop_column("ingestion_jobs", "visibility")
    op.drop_column("ingestion_jobs", "owner_id")
    op.drop_column("documents", "allowed_group_ids")
    op.drop_column("documents", "allowed_user_ids")
    op.drop_column("documents", "visibility")
    op.drop_column("documents", "owner_id")

