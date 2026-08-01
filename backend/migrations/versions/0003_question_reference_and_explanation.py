"""Add a Bible reference and a one-line explanation to each question.

Both are revealed with the answer key, so a player who gets one wrong learns
why — and a disputed answer has a citation behind it.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-01 14:26:07.262894
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


AUTO_STRING = sqlmodel.sql.sqltypes.AutoString()


def upgrade() -> None:
    with op.batch_alter_table("question", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reference", AUTO_STRING, nullable=True))
        batch_op.add_column(sa.Column("explanation", AUTO_STRING, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("question", schema=None) as batch_op:
        batch_op.drop_column("explanation")
        batch_op.drop_column("reference")
