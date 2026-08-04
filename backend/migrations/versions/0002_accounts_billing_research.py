"""Accounts, billing fields and the research/questionnaire tables.

Adds everything the launch work introduced:

- `player.password_hash` / `deleted_at` — real logins and GDPR account deletion
- `player.subscription_cancel_at_period_end` / `billing_*` — subscription state
- `researchconsent`, `questionnairecompletion`, `questionnaireanswer`

The `DuelStatus.DECLINED` value needs no DDL: SQLAlchemy stores enums as VARCHAR
without a CHECK constraint by default, so the new value is already accepted.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

QUESTIONNAIRE_TYPE_ENUM = sa.Enum(
    "FAITH_BACKGROUND", "ADHD_SCREENER", "AUTISM_SCREENER", name="questionnairetype"
)


def upgrade() -> None:
    with op.batch_alter_table("player", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("password_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "subscription_cancel_at_period_end",
                sa.Boolean(),
                nullable=False,
                # A NOT NULL column needs a default for the rows that already
                # exist. sa.false() renders per dialect — Postgres rejects the
                # integer literal 0 for a boolean column.
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("billing_customer_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("billing_subscription_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_player_billing_customer_id"), ["billing_customer_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_player_billing_subscription_id"),
            ["billing_subscription_id"],
            unique=False,
        )

    op.create_table(
        "researchconsent",
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("research_uuid", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("consented_at", sa.DateTime(), nullable=False),
        sa.Column("consent_version", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("health_data_consent", sa.Boolean(), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["player.id"]),
        sa.PrimaryKeyConstraint("player_id"),
    )
    with op.batch_alter_table("researchconsent", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_researchconsent_research_uuid"), ["research_uuid"], unique=True
        )

    op.create_table(
        "questionnairecompletion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("research_uuid", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("questionnaire_type", QUESTIONNAIRE_TYPE_ENUM, nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("questionnairecompletion", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_questionnairecompletion_research_uuid"), ["research_uuid"], unique=False
        )

    op.create_table(
        "questionnaireanswer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("completion_id", sa.Integer(), nullable=False),
        sa.Column("question_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("response_value", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["completion_id"], ["questionnairecompletion.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("completion_id", "question_key", name="uq_answer_per_question"),
    )
    with op.batch_alter_table("questionnaireanswer", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_questionnaireanswer_completion_id"), ["completion_id"], unique=False
        )


def downgrade() -> None:
    op.drop_table("questionnaireanswer")
    op.drop_table("questionnairecompletion")
    op.drop_table("researchconsent")
    QUESTIONNAIRE_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("player", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_player_billing_subscription_id"))
        batch_op.drop_index(batch_op.f("ix_player_billing_customer_id"))
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("billing_subscription_id")
        batch_op.drop_column("billing_customer_id")
        batch_op.drop_column("subscription_cancel_at_period_end")
        batch_op.drop_column("password_hash")
