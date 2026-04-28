"""add citation score

Revision ID: 0002_add_citation_score
Revises: 0001_initial_schema
Create Date: 2026-04-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_citation_score"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("citations", sa.Column("score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("citations", "score")

