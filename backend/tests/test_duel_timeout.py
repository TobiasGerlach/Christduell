from datetime import timedelta

import pytest
from sqlmodel import select

from app.core.time import utcnow
from app.models.domain import Category, DuelAnswer
from tests.factories import make_questions_for_category


@pytest.fixture(name="round_id")
def round_fixture(session, duel):
    """Starts a round and shows the challenger the first question."""
    make_questions_for_category(session, Category.HISTORY, 3)
    pick_resp = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds", json={"category": Category.HISTORY.value}
    )
    round_id = pick_resp.json()["round_id"]
    duel.challenger.get(f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1")
    return round_id


def test_explicit_null_choice_is_recorded_as_timeout(duel, round_id):
    result = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1/answer",
        json={"selected_choice_index": None},
    ).json()

    assert result["is_timeout"] is True
    assert result["is_correct"] is False


def test_late_submission_forced_to_timeout_even_with_a_choice(session, duel, round_id):
    answer = session.exec(
        select(DuelAnswer).where(
            DuelAnswer.round_id == round_id, DuelAnswer.player_id == duel.challenger.id
        )
    ).one()
    answer.shown_at = utcnow() - timedelta(seconds=45)
    session.add(answer)
    session.commit()

    result = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1/answer",
        json={"selected_choice_index": 0},
    ).json()

    # The server is authoritative on timing — a late submission is forced to a
    # timeout (and thus incorrect) regardless of what choice the client sent.
    assert result["is_timeout"] is True
    assert result["is_correct"] is False

    session.refresh(answer)
    assert answer.selected_choice_index == 0  # late choice is still stored for display
    assert answer.is_timeout is True
    assert answer.is_correct is False
