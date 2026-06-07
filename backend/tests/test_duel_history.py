from types import SimpleNamespace

import pytest

from app.models.domain import Category
from tests.factories import make_player, make_questions_for_category


@pytest.fixture(name="duel")
def duel_fixture(client, session):
    challenger = make_player(session, "Challenger", "challenger@test.local")
    opponent = make_player(session, "Opponent", "opponent@test.local")
    create_resp = client.post(
        "/duels", json={"challenger_id": challenger.id, "opponent_id": opponent.id}
    )
    return SimpleNamespace(duel_id=create_resp.json()["id"], challenger=challenger, opponent=opponent)


def _answer_all(client, duel_id, round_id, player_id):
    for position in (1, 2, 3):
        client.get(
            f"/duels/{duel_id}/rounds/{round_id}/questions/{position}",
            params={"player_id": player_id},
        )
        client.post(
            f"/duels/{duel_id}/rounds/{round_id}/questions/{position}/answer",
            json={"player_id": player_id, "selected_choice_index": 0},
        )


def test_opponent_answers_hidden_pre_reveal_then_visible_post_reveal(client, session, duel):
    make_questions_for_category(session, Category.PSALMS_PRAYERS, 3)
    pick_resp = client.post(
        f"/duels/{duel.duel_id}/rounds",
        json={"player_id": duel.challenger.id, "category": Category.PSALMS_PRAYERS.value},
    )
    round_id = pick_resp.json()["round_id"]

    # Picker (first responder) finishes their three answers; the round is not
    # revealed yet because the second responder hasn't gone.
    _answer_all(client, duel.duel_id, round_id, duel.challenger.id)

    history_before = client.get(
        f"/duels/{duel.duel_id}/history", params={"player_id": duel.opponent.id}
    ).json()
    round_before = next(r for r in history_before["rounds"] if r["sequence"] == 1)
    assert round_before["revealed"] is False
    for question in round_before["questions"]:
        assert question["correct_choice_index"] is None
        # The opponent hasn't answered yet, and the challenger's answers are
        # hidden until both have completed the round.
        assert question["answers"] == []

    # Now the second responder (opponent) answers — the round reveals.
    _answer_all(client, duel.duel_id, round_id, duel.opponent.id)

    history_after = client.get(
        f"/duels/{duel.duel_id}/history", params={"player_id": duel.opponent.id}
    ).json()
    round_after = next(r for r in history_after["rounds"] if r["sequence"] == 1)
    assert round_after["revealed"] is True
    for question in round_after["questions"]:
        assert question["correct_choice_index"] == 0
        assert {a["player_id"] for a in question["answers"]} == {duel.challenger.id, duel.opponent.id}
        assert all(a["is_correct"] is True for a in question["answers"])
