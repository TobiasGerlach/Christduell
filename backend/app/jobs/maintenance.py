"""Periodic housekeeping. Run with `uv run python -m app.jobs.maintenance`.

Currently one job: move players whose paid period has elapsed back to the
research tier. Entitlement checks already treat a lapsed subscription as
inactive, so this only keeps the stored tier honest — but without it, a player
who stopped paying would never be asked for questionnaires again.
"""

import logging

from sqlmodel import Session

from app.db.session import engine, init_db
from app.services.subscriptions import downgrade_expired_subscriptions

logger = logging.getLogger(__name__)


def run() -> int:
    # Same reason as in question_reports: a job is not the app booting.
    init_db()
    with Session(engine) as session:
        downgraded = downgrade_expired_subscriptions(session)
    logger.info("maintenance: downgraded %d expired subscription(s)", downgraded)
    return downgraded


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(f"Downgraded {run()} expired subscription(s)")
