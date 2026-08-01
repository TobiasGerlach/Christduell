from datetime import UTC, datetime


def utcnow() -> datetime:
    """Current UTC time as a naive datetime.

    All timestamp columns store naive UTC. `datetime.utcnow()` is deprecated,
    but switching the columns to timezone-aware values would break comparisons
    against every row already written, so we strip the tzinfo back off here and
    keep a single definition of "now" for the whole app.
    """
    return datetime.now(UTC).replace(tzinfo=None)
