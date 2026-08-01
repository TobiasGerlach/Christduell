"""The migrations must describe exactly what the models describe.

`create_all` hides schema drift (it only creates missing tables), so this test
is the guard: it runs the real migration chain against a scratch database and
compares the result to SQLModel's metadata. A model change without a matching
migration fails here rather than in production.
"""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel

from app.db.session import BACKEND_DIR


def _alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_migrations_match_the_models(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'migrated.db'}"
    command.upgrade(_alembic_config(database_url), "head")

    inspector = inspect(create_engine(database_url))
    migrated = {
        name: {column["name"] for column in inspector.get_columns(name)}
        for name in inspector.get_table_names()
        if name != "alembic_version"
    }
    expected = {
        name: set(table.columns.keys()) for name, table in SQLModel.metadata.tables.items()
    }
    assert migrated == expected


def test_migrations_downgrade_cleanly(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'roundtrip.db'}"
    config = _alembic_config(database_url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    inspector = inspect(create_engine(database_url))
    assert [t for t in inspector.get_table_names() if t != "alembic_version"] == []
