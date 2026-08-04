"""Closing duels that nobody is playing any more.

Without this, a player who quits mid-duel leaves the opponent staring at
"opponent's turn" forever, and the pair is excluded from random matchmaking for
good. Run from the maintenance job.

A pending challenge that was never answered simply disappears (declined); an
active duel ends at the current score, which usually favours whoever kept
playing — good enough, and far simpler than a forfeit concept.
"""

import logging
from datetime import datetime, timedelta

from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.time import utcnow
from app.models.domain import Duel, DuelAnswer, DuelRound, DuelStatus
from app.services.notifications import notify_duel_finished

logger = logging.getLogger(__name__)


def last_activity(session: Session, duel: Duel) -> datetime:
    """The most recent thing anyone did in this duel."""
    moments = [duel.created_at]
    rounds = list(session.exec(select(DuelRound).where(DuelRound.duel_id == duel.id)))
    moments.extend(r.created_at for r in rounds)
    round_ids = [r.id for r in rounds]
    if round_ids:
        answers = session.exec(
            select(DuelAnswer).where(col(DuelAnswer.round_id).in_(round_ids))
        )
        for answer in answers:
            moments.append(answer.shown_at)
            if answer.answered_at is not None:
                moments.append(answer.answered_at)
    return max(moments)


def expire_inactive_duels(session: Session, now: datetime | None = None) -> int:
    """Closes open duels with no activity for the configured number of days."""
    moment = now or utcnow()
    cutoff = moment - timedelta(days=get_settings().duel_inactivity_expiry_days)

    open_duels = list(
        session.exec(
            select(Duel).where(col(Duel.status).in_([DuelStatus.PENDING, DuelStatus.ACTIVE]))
        )
    )

    expired = 0
    for duel in open_duels:
        if last_activity(session, duel) >= cutoff:
            continue
        if duel.status == DuelStatus.PENDING:
            # A challenge nobody answered — no scores, nothing to announce.
            duel.status = DuelStatus.DECLINED
        else:
            duel.status = DuelStatus.FINISHED
            duel.finished_at = moment
        session.add(duel)
        session.commit()
        if duel.status == DuelStatus.FINISHED:
            notify_duel_finished(session, duel)
        expired += 1

    if expired:
        logger.info("expired %d inactive duel(s)", expired)
    return expired
