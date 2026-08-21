"""Web Push subscriptions for the browser/PWA build.

One row per browser push endpoint. Endpoints identify a browser profile, not a
person — unique, and reassigned to whoever signs in on that browser.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webpushsubscription",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("p256dh", sa.String(), nullable=False),
        sa.Column("auth", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["player.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_webpushsubscription_player_id"), "webpushsubscription", ["player_id"]
    )
    op.create_index(
        op.f("ix_webpushsubscription_endpoint"),
        "webpushsubscription",
        ["endpoint"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_webpushsubscription_endpoint"), table_name="webpushsubscription")
    op.drop_index(op.f("ix_webpushsubscription_player_id"), table_name="webpushsubscription")
    op.drop_table("webpushsubscription")
