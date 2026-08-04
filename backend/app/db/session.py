import logging
from collections.abc import Generator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import event, text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# backend/ — where alembic.ini and migrations/ live.
BACKEND_DIR = Path(__file__).resolve().parents[2]

# Arbitrary but fixed: every instance must ask for the same lock.
MIGRATION_LOCK_KEY = 8_147_320_591

settings = get_settings()
IS_SQLITE = settings.database_url.startswith("sqlite")

if IS_SQLITE:
    # Local development and tests. One writer at a time, which is fine for a
    # single developer and unacceptable for production — see infra/README.md.
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        # Wait for a contended write instead of failing the request outright.
        dbapi_conn.execute("PRAGMA busy_timeout=5000")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
else:
    engine = create_engine(
        settings.database_url,
        # Azure closes idle connections; without this the first query after a
        # quiet spell fails on a dead socket.
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=1800,
    )


def run_migrations() -> None:
    """Brings the database up to the newest revision.

    Safe to run on every boot: Alembic no-ops when the database is already at
    head. This is what keeps the deployed SQLite file in step with the models —
    `create_all` only ever creates missing tables and would silently skip new
    columns on tables that already exist.
    """
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    if IS_SQLITE:
        command.upgrade(config, "head")
        return

    # On Postgres several instances can boot at once (a deploy overlaps the old
    # and new container). An advisory lock makes them queue instead of running
    # Alembic concurrently; the ones that lose the race then find nothing to do.
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        try:
            command.upgrade(config, "head")
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY}
            )


def init_db() -> None:
    if settings.auto_migrate:
        run_migrations()
    else:
        logger.warning("AUTO_MIGRATE is off — creating any missing tables without migrations")
        SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
