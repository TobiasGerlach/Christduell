import logging
from collections.abc import Generator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# backend/ — where alembic.ini and migrations/ live.
BACKEND_DIR = Path(__file__).resolve().parents[2]

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)

if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_wal_mode(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")


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
    command.upgrade(config, "head")


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
