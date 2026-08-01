"""Initial schema: players, questions and the duel engine.

This is the schema as it stood before accounts, billing and the research module
existed. An environment whose database predates Alembic is brought under
control with `alembic stamp 0001` followed by `alembic upgrade head` — that
applies 0002 without trying to recreate tables that are already there.

Revision ID: 0001
Revises:
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORY_ENUM = sa.Enum(
    "OLD_TESTAMENT",
    "NEW_TESTAMENT",
    "BEYOND_THE_HORIZON",
    "ANCIENT_LANGUAGES",
    "HISTORY",
    "JESUS_TODAY",
    "CHURCH_YEAR_FESTIVALS",
    "PARABLES_MIRACLES",
    "PSALMS_PRAYERS",
    "SYMBOLS_CUSTOMS",
    "SAINTS_ROLE_MODELS",
    "FACTS_NUMBERS_DATES",
    "FAITH_POP_CULTURE",
    name="category",
)


def upgrade() -> None:
    op.create_table(
        "player",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("display_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("push_token", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column(
            "subscription_tier",
            sa.Enum("RESEARCH", "PAID", name="subscriptiontier"),
            nullable=False,
        ),
        sa.Column("subscription_valid_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("player", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_player_email"), ["email"], unique=True)

    op.create_table(
        "question",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category", CATEGORY_ENUM, nullable=False),
        sa.Column("prompt", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("choices", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("correct_choice_index", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "duel",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("challenger_id", sa.Integer(), nullable=False),
        sa.Column("opponent_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACTIVE", "FINISHED", "DECLINED", name="duelstatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["challenger_id"], ["player.id"]),
        sa.ForeignKeyConstraint(["opponent_id"], ["player.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "duelround",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("duel_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("category", CATEGORY_ENUM, nullable=False),
        sa.Column("picked_by_id", sa.Integer(), nullable=False),
        sa.Column("first_responder_id", sa.Integer(), nullable=False),
        sa.Column("second_responder_id", sa.Integer(), nullable=False),
        sa.Column("first_responder_completed_at", sa.DateTime(), nullable=True),
        sa.Column("second_responder_completed_at", sa.DateTime(), nullable=True),
        sa.Column("revealed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["duel_id"], ["duel.id"]),
        sa.ForeignKeyConstraint(["first_responder_id"], ["player.id"]),
        sa.ForeignKeyConstraint(["picked_by_id"], ["player.id"]),
        sa.ForeignKeyConstraint(["second_responder_id"], ["player.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("duel_id", "category", name="uq_duel_round_category"),
        sa.UniqueConstraint("duel_id", "sequence", name="uq_duel_round_sequence"),
    )
    with op.batch_alter_table("duelround", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_duelround_duel_id"), ["duel_id"], unique=False)

    op.create_table(
        "duelroundquestion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("round_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"]),
        sa.ForeignKeyConstraint(["round_id"], ["duelround.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("round_id", "position", name="uq_round_question_position"),
    )
    with op.batch_alter_table("duelroundquestion", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_duelroundquestion_round_id"), ["round_id"], unique=False
        )

    op.create_table(
        "duelanswer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("round_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("shown_at", sa.DateTime(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column("selected_choice_index", sa.Integer(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("is_timeout", sa.Boolean(), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["player.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"]),
        sa.ForeignKeyConstraint(["round_id"], ["duelround.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("round_id", "question_id", "player_id", name="uq_duel_answer_identity"),
    )
    with op.batch_alter_table("duelanswer", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_duelanswer_player_id"), ["player_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_duelanswer_round_id"), ["round_id"], unique=False)


def downgrade() -> None:
    op.drop_table("duelanswer")
    op.drop_table("duelroundquestion")
    op.drop_table("duelround")
    op.drop_table("duel")
    op.drop_table("question")
    op.drop_table("player")
