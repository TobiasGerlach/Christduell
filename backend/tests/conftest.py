import os
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core import ratelimit
from app.core.config import get_settings
from app.db.session import get_session
from app.main import app
from app.models.domain import Category
from app.services import push
from tests.factories import PlayerClient, make_player

# Set TEST_DATABASE_URL to run the whole suite against a real Postgres:
#   TEST_DATABASE_URL=postgresql+psycopg://user@localhost/christduell_test uv run pytest
# Without it, tests use an in-memory SQLite, which is far quicker.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(name="session")
def session_fixture():
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL)
        # Each test starts from an empty schema so ordering can't matter.
        SQLModel.metadata.drop_all(engine)
        SQLModel.metadata.create_all(engine)
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


@pytest.fixture(name="client")
def client_fixture(session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clean_rate_limits():
    """The limiter is process-global; without this, login failures in one test
    would count against the same address in the next."""
    ratelimit.limiter.reset()
    yield
    ratelimit.limiter.reset()


@pytest.fixture(name="settings_override")
def settings_override_fixture(monkeypatch):
    """Sets settings fields for one test and restores the cache afterwards.

    `get_settings` is lru_cached, so the cached instance is patched in place and
    then cleared — that way anything holding a reference sees the change too.
    """
    settings = get_settings()
    originals: dict[str, object] = {}

    def override(**values):
        for key, value in values.items():
            if key not in originals:
                originals[key] = getattr(settings, key)
            monkeypatch.setattr(settings, key, value, raising=False)
        return settings

    yield override

    for key, value in originals.items():
        setattr(settings, key, value)
    get_settings.cache_clear()


@pytest.fixture(name="captured_pushes")
def captured_pushes_fixture(monkeypatch) -> list[push.PushMessage]:
    """Collects the push messages the app tried to send."""
    sent: list[push.PushMessage] = []
    monkeypatch.setattr(push, "send", lambda messages: sent.extend(messages))
    return sent


@pytest.fixture(name="duel")
def duel_fixture(client, session):
    """Two registered players and a fresh duel between them.

    `duel.challenger` / `duel.opponent` are `PlayerClient`s — call the API
    through them to act as that player.
    """
    challenger = PlayerClient(client, make_player(session, "Challenger", "challenger@example.com"))
    opponent = PlayerClient(client, make_player(session, "Opponent", "opponent@example.com"))

    create_resp = challenger.post("/duels", json={"opponent_id": opponent.id})
    assert create_resp.status_code == 201, create_resp.text

    return SimpleNamespace(
        duel_id=create_resp.json()["id"],
        challenger=challenger,
        opponent=opponent,
    )


@pytest.fixture(name="categories")
def categories_fixture() -> list[Category]:
    return list(Category)
