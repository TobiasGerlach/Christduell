"""Periodic housekeeping. Run with `uv run python -m app.jobs.maintenance`.

Two jobs: move players whose paid period has elapsed back to the research tier,
and close duels that nobody has touched for a while — otherwise an abandoned
duel shows "opponent's turn" forever and blocks that pairing in matchmaking.
"""

import logging

from sqlmodel import Session

from app.db.session import engine, init_db
from app.services.duel_expiry import expire_inactive_duels
from app.services.subscriptions import downgrade_expired_subscriptions

logger = logging.getLogger(__name__)


def run() -> tuple[int, int]:
    # Same reason as in question_reports: a job is not the app booting.
    init_db()
    with Session(engine) as session:
        downgraded = downgrade_expired_subscriptions(session)
        expired = expire_inactive_duels(session)
    logger.info(
        "maintenance: downgraded %d subscription(s), expired %d duel(s)", downgraded, expired
    )
    return downgraded, expired


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    downgraded, expired = run()
    print(f"Downgraded {downgraded} expired subscription(s), expired {expired} inactive duel(s)")
