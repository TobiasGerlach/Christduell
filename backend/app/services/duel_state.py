from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.domain import Duel, DuelAnswer, DuelRound, DuelStatus

TOTAL_ROUNDS = 8
QUESTIONS_PER_ROUND = 3


class DuelAction(StrEnum):
    PICK_CATEGORY = "pick_category"
    ANSWER_QUESTION = "answer_question"
    FINISHED = "finished"


@dataclass
class DuelState:
    action: DuelAction
    acting_player_id: int | None
    waiting_player_id: int | None
    round_sequence: int | None
    round_id: int | None
    position: int | None


def completed_answer_count(session: Session, round_id: int, player_id: int) -> int:
    statement = (
        select(func.count())
        .select_from(DuelAnswer)
        .where(
            DuelAnswer.round_id == round_id,
            DuelAnswer.player_id == player_id,
            DuelAnswer.answered_at.is_not(None),
        )
    )
    return session.exec(statement).one()


def compute_duel_state(session: Session, duel: Duel) -> DuelState:
    """Single source of truth for whose turn it is and what they must do.

    Used both to answer `GET .../state` and as the validation gate inside
    every mutating endpoint (compare the requesting player to
    `acting_player_id` — that one check rules out out-of-turn picks/answers,
    skipped positions, second-responder-before-first, and double submission).
    """
    # A closed duel is closed regardless of what its rounds look like. Expiry
    # can finish a duel mid-round, and without this early return the rounds
    # would still say "someone should answer" — which the routes would allow.
    if duel.status in (DuelStatus.FINISHED, DuelStatus.DECLINED):
        return DuelState(
            action=DuelAction.FINISHED,
            acting_player_id=None,
            waiting_player_id=None,
            round_sequence=None,
            round_id=None,
            position=None,
        )

    rounds = list(
        session.exec(
            select(DuelRound).where(DuelRound.duel_id == duel.id).order_by(DuelRound.sequence)
        )
    )
    n = len(rounds)

    if n == 0:
        return DuelState(
            action=DuelAction.PICK_CATEGORY,
            acting_player_id=duel.challenger_id,
            waiting_player_id=duel.opponent_id,
            round_sequence=1,
            round_id=None,
            position=None,
        )

    current = rounds[-1]

    if current.revealed_at is not None:
        if n == TOTAL_ROUNDS:
            return DuelState(
                action=DuelAction.FINISHED,
                acting_player_id=None,
                waiting_player_id=None,
                round_sequence=None,
                round_id=None,
                position=None,
            )
        return DuelState(
            action=DuelAction.PICK_CATEGORY,
            acting_player_id=current.second_responder_id,
            waiting_player_id=current.first_responder_id,
            round_sequence=n + 1,
            round_id=None,
            position=None,
        )

    first, second = current.first_responder_id, current.second_responder_id
    first_done = completed_answer_count(session, current.id, first)
    if first_done < QUESTIONS_PER_ROUND:
        return DuelState(
            action=DuelAction.ANSWER_QUESTION,
            acting_player_id=first,
            waiting_player_id=second,
            round_sequence=current.sequence,
            round_id=current.id,
            position=first_done + 1,
        )

    second_done = completed_answer_count(session, current.id, second)
    if second_done < QUESTIONS_PER_ROUND:
        return DuelState(
            action=DuelAction.ANSWER_QUESTION,
            acting_player_id=second,
            waiting_player_id=first,
            round_sequence=current.sequence,
            round_id=current.id,
            position=second_done + 1,
        )

    # Both players have completed all 3 questions but the round isn't marked
    # revealed yet. The answer endpoint sets `revealed_at` atomically with the
    # 3rd second-responder answer, so this should never be observable —
    # treated as "finished" defensively rather than raising.
    return DuelState(
        action=DuelAction.FINISHED if n == TOTAL_ROUNDS else DuelAction.PICK_CATEGORY,
        acting_player_id=None if n == TOTAL_ROUNDS else second,
        waiting_player_id=None if n == TOTAL_ROUNDS else first,
        round_sequence=None if n == TOTAL_ROUNDS else n + 1,
        round_id=None,
        position=None,
    )


def compute_duel_scores(session: Session, duel: Duel) -> tuple[int, int]:
    """Returns (challenger_score, opponent_score) as counts of correct answers.

    Computed on read rather than stored, to avoid drift — at most 24 answers
    per duel, cheap to aggregate.
    """

    def score_for(player_id: int) -> int:
        statement = (
            select(func.count())
            .select_from(DuelAnswer)
            .join(DuelRound, DuelAnswer.round_id == DuelRound.id)
            .where(
                DuelRound.duel_id == duel.id,
                DuelAnswer.player_id == player_id,
                DuelAnswer.is_correct.is_(True),
            )
        )
        return session.exec(statement).one()

    return score_for(duel.challenger_id), score_for(duel.opponent_id)
