"""Player reports about questions, and the self-healing that follows.

The question bank is large enough that reading every entry is impractical, so
players are the review mechanism: anyone who has actually answered a question can
report it, and once enough distinct players agree, the question retires itself
and stops being dealt into new rounds. Nobody has to be awake for that to happen.

Retirement is reversible and destroys nothing — the reports and the question stay
in the database for whoever triages them later (`make reports`).
"""

import logging

from sqlmodel import Session, col, func, select

from app.core.config import get_settings
from app.core.time import utcnow
from app.models.domain import (
    DuelAnswer,
    Question,
    QuestionReport,
    ReportReason,
    ReportStatus,
)

logger = logging.getLogger(__name__)

# Only disagreements about correctness retire a question. A typo is worth
# knowing about but is no reason to pull the question out of circulation.
RETIRING_REASONS = {ReportReason.WRONG_ANSWER, ReportReason.AMBIGUOUS}


def has_answered(session: Session, player_id: int, question_id: int) -> bool:
    """Whether this player has actually been shown the question.

    Reporting is limited to questions you have played, which keeps the endpoint
    from being a way to retire arbitrary questions you have never seen.
    """
    answer = session.exec(
        select(DuelAnswer.id).where(
            DuelAnswer.player_id == player_id,
            DuelAnswer.question_id == question_id,
        )
    ).first()
    return answer is not None


def existing_report(session: Session, player_id: int, question_id: int) -> QuestionReport | None:
    return session.exec(
        select(QuestionReport).where(
            QuestionReport.player_id == player_id,
            QuestionReport.question_id == question_id,
        )
    ).first()


def count_retiring_reports(session: Session, question_id: int) -> int:
    """Distinct open reports that dispute the question's correctness."""
    statement = (
        select(func.count())
        .select_from(QuestionReport)
        .where(
            QuestionReport.question_id == question_id,
            QuestionReport.status == ReportStatus.OPEN,
            col(QuestionReport.reason).in_(RETIRING_REASONS),
        )
    )
    return session.exec(statement).one()


def report_question(
    session: Session,
    *,
    question: Question,
    player_id: int,
    reason: ReportReason,
    note: str | None = None,
) -> tuple[QuestionReport, bool]:
    """Records a report. Returns it plus whether it retired the question."""
    report = existing_report(session, player_id, question.id)
    if report is None:
        report = QuestionReport(
            question_id=question.id,
            player_id=player_id,
            reason=reason,
            note=(note or "").strip() or None,
        )
    else:
        # Someone changing their mind updates their report rather than adding one.
        report.reason = reason
        report.note = (note or "").strip() or None
        report.status = ReportStatus.OPEN
        report.resolved_at = None

    session.add(report)
    session.commit()
    session.refresh(report)

    retired = maybe_retire(session, question)
    return report, retired


def maybe_retire(session: Session, question: Question) -> bool:
    """Retires the question if enough players dispute it. Returns True if it did."""
    if question.retired_at is not None:
        return False

    threshold = get_settings().question_report_retire_threshold
    if count_retiring_reports(session, question.id) < threshold:
        return False

    question.retired_at = utcnow()
    session.add(question)
    session.commit()
    logger.warning(
        "question %s retired after %d reports: %s",
        question.id,
        threshold,
        question.prompt[:80],
    )
    return True


def restore(session: Session, question: Question) -> Question:
    """Puts a question back into circulation and closes its open reports."""
    question.retired_at = None
    session.add(question)
    for report in session.exec(
        select(QuestionReport).where(
            QuestionReport.question_id == question.id,
            QuestionReport.status == ReportStatus.OPEN,
        )
    ):
        report.status = ReportStatus.DISMISSED
        report.resolved_at = utcnow()
        session.add(report)
    session.commit()
    session.refresh(question)
    return question


def resolve(session: Session, question_id: int, status: ReportStatus) -> int:
    """Closes every open report on a question. Returns how many were closed."""
    reports = list(
        session.exec(
            select(QuestionReport).where(
                QuestionReport.question_id == question_id,
                QuestionReport.status == ReportStatus.OPEN,
            )
        )
    )
    for report in reports:
        report.status = status
        report.resolved_at = utcnow()
        session.add(report)
    session.commit()
    return len(reports)
