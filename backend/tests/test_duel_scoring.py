from types import SimpleNamespace

import pytest

from app.models.domain import Category
from tests.factories import make_player, make_questions_for_category, play_round


@pytest.fixture(name="duel")
def duel_fixture(client, session):
    challenger = make_player(session, "Challenger", "challenger@test.local")
    opponent = make_player(session, "Opponent", "opponent@test.local")
    create_resp = client.post(
        "/duels", json={"challenger_id": challenger.id, "opponent_id": opponent.id}
    )
    return SimpleNamespace(duel_id=create_resp.json()["id"], challenger=challenger, opponent=opponent)


def test_scores_count_only_correct_answers(client, session, duel):
    play_round(
        client,
        session,
        duel.duel_id,
        duel.challenger.id,
        duel.opponent.id,
        Category.OLD_TESTAMENT,
        picker_choices=(0, 1, 0),  # 2 correct (question's correct index is always 0)
        responder_choices=(0, 0, 1),  # 2 correct
    )

    summaries = client.get("/duels", params={"player_id": duel.challenger.id}).json()
    item = next(d for d in summaries if d["id"] == duel.duel_id)
    assert item["challenger_score"] == 2
    assert item["opponent_score"] == 2

    state = client.get(f"/duels/{duel.duel_id}/state", params={"player_id": duel.challenger.id}).json()
    assert state["challenger_score"] == 2
    assert state["opponent_score"] == 2


def test_correctness_is_computed_server_side_from_question_answer_key(client, session, duel):
    make_questions_for_category(session, Category.NEW_TESTAMENT, 3)
    pick_resp = client.post(
        f"/duels/{duel.duel_id}/rounds",
        json={"player_id": duel.challenger.id, "category": Category.NEW_TESTAMENT.value},
    )
    round_id = pick_resp.json()["round_id"]

    client.get(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1",
        params={"player_id": duel.challenger.id},
    )
    correct = client.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1/answer",
        json={"player_id": duel.challenger.id, "selected_choice_index": 0},
    ).json()
    assert correct["is_correct"] is True
    assert correct["correct_choice_index"] == 0

    client.get(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/2",
        params={"player_id": duel.challenger.id},
    )
    wrong = client.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/2/answer",
        json={"player_id": duel.challenger.id, "selected_choice_index": 3},
    ).json()
    assert wrong["is_correct"] is False
    assert wrong["correct_choice_index"] == 0
