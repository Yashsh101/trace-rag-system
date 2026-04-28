"""add query observability json

Revision ID: 0003_add_query_observability
Revises: 0002_add_citation_score
Create Date: 2026-04-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_query_observability"
down_revision: Union[str, None] = "0002_add_citation_score"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("query_logs", sa.Column("trace_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
    op.add_column("query_logs", sa.Column("metrics_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
    op.add_column("query_logs", sa.Column("validation_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))


def downgrade() -> None:
    op.drop_column("query_logs", "validation_json")
    op.drop_column("query_logs", "metrics_json")
    op.drop_column("query_logs", "trace_json")

