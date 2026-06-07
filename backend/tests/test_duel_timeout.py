from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlmodel import select

from app.models.domain import Category, DuelAnswer
from tests.factories import make_player, make_questions_for_category


@pytest.fixture(name="duel")
def duel_fixture(client, session):
    challenger = make_player(session, "Challenger", "challenger@test.local")
    opponent = make_player(session, "Opponent", "opponent@test.local")
    create_resp = client.post(
        "/duels", json={"challenger_id": challenger.id, "opponent_id": opponent.id}
    )
    return SimpleNamespace(duel_id=create_resp.json()["id"], challenger=challenger, opponent=opponent)


def _start_round_and_show_first_question(client, session, duel):
    make_questions_for_category(session, Category.HISTORY, 3)
    pick_resp = client.post(
        f"/duels/{duel.duel_id}/rounds",
        json={"player_id": duel.challenger.id, "category": Category.HISTORY.value},
    )
    round_id = pick_resp.json()["round_id"]
    client.get(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1",
        params={"player_id": duel.challenger.id},
    )
    return round_id


def test_explicit_null_choice_is_recorded_as_timeout(client, session, duel):
    round_id = _start_round_and_show_first_question(client, session, duel)

    result = client.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1/answer",
        json={"player_id": duel.challenger.id, "selected_choice_index": None},
    ).json()

    assert result["is_timeout"] is True
    assert result["is_correct"] is False


def test_late_submission_forced_to_timeout_even_with_a_choice(client, session, duel):
    round_id = _start_round_and_show_first_question(client, session, duel)

    answer = session.exec(
        select(DuelAnswer).where(
            DuelAnswer.round_id == round_id, DuelAnswer.player_id == duel.challenger.id
        )
    ).one()
    answer.shown_at = datetime.utcnow() - timedelta(seconds=45)
    session.add(answer)
    session.commit()

    result = client.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1/answer",
        json={"player_id": duel.challenger.id, "selected_choice_index": 0},
    ).json()

    # The server is authoritative on timing — a late submission is forced to a
    # timeout (and thus incorrect) regardless of what choice the client sent.
    assert result["is_timeout"] is True
    assert result["is_correct"] is False

    session.refresh(answer)
    assert answer.selected_choice_index == 0  # late choice is still stored for display
    assert answer.is_timeout is True
    assert answer.is_correct is False
