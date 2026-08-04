"""Record the age confirmation given at registration.

GDPR Art. 8 sets the consent age in Germany at 16; registration now requires
confirming it (or parental consent), and this column is the record that it
happened. Nullable, because rows created before the checkbox existed cannot
retroactively have confirmed anything.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("player", schema=None) as batch_op:
        batch_op.add_column(sa.Column("min_age_confirmed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("player", schema=None) as batch_op:
        batch_op.drop_column("min_age_confirmed_at")
