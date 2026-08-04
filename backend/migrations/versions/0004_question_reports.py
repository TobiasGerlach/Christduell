"""Player-reported problems with questions.

Players are the review mechanism for a bank too large to proofread by hand: a
question that enough of them dispute sets `question.retired_at` and stops being
dealt, while the reports stay for triage.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-01 17:37:19.867343
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUTO_STRING = sqlmodel.sql.sqltypes.AutoString()
REASON_ENUM = sa.Enum(
    "WRONG_ANSWER", "AMBIGUOUS", "TYPO", "INAPPROPRIATE", "OTHER", name="reportreason"
)
STATUS_ENUM = sa.Enum("OPEN", "RESOLVED", "DISMISSED", name="reportstatus")


def upgrade() -> None:
    op.create_table('questionreport',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('player_id', sa.Integer(), nullable=False),
    sa.Column("reason", REASON_ENUM, nullable=False),
    sa.Column('note', AUTO_STRING, nullable=True),
    sa.Column("status", STATUS_ENUM, nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['player_id'], ['player.id'], ),
    sa.ForeignKeyConstraint(['question_id'], ['question.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('question_id', 'player_id', name='uq_report_per_player')
    )
    with op.batch_alter_table('questionreport', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_questionreport_player_id"), ['player_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_questionreport_question_id"), ['question_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_questionreport_status"), ['status'], unique=False
        )

    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("retired_at", sa.DateTime(), nullable=True)
        )



def downgrade() -> None:
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.drop_column('retired_at')

    with op.batch_alter_table('questionreport', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_questionreport_status'))
        batch_op.drop_index(batch_op.f('ix_questionreport_question_id'))
        batch_op.drop_index(batch_op.f('ix_questionreport_player_id'))

    op.drop_table('questionreport')
    for enum in (REASON_ENUM, STATUS_ENUM):
        enum.drop(op.get_bind(), checkfirst=True)
