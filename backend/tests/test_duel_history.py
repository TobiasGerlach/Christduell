from app.models.domain import Category
from tests.factories import answer_all_questions, make_questions_for_category


def test_opponent_answers_hidden_pre_reveal_then_visible_post_reveal(session, duel):
    make_questions_for_category(session, Category.PSALMS_PRAYERS, 3)
    pick_resp = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds", json={"category": Category.PSALMS_PRAYERS.value}
    )
    round_id = pick_resp.json()["round_id"]

    # Picker (first responder) finishes their three answers; the round is not
    # revealed yet because the second responder hasn't gone.
    answer_all_questions(duel.challenger, duel.duel_id, round_id)

    history_before = duel.opponent.get(f"/duels/{duel.duel_id}/history").json()
    round_before = next(r for r in history_before["rounds"] if r["sequence"] == 1)
    assert round_before["revealed"] is False
    for question in round_before["questions"]:
        assert question["correct_choice_index"] is None
        # The opponent hasn't answered yet, and the challenger's answers are
        # hidden until both have completed the round.
        assert question["answers"] == []

    # Now the second responder (opponent) answers — the round reveals.
    answer_all_questions(duel.opponent, duel.duel_id, round_id)

    history_after = duel.opponent.get(f"/duels/{duel.duel_id}/history").json()
    round_after = next(r for r in history_after["rounds"] if r["sequence"] == 1)
    assert round_after["revealed"] is True
    for question in round_after["questions"]:
        assert question["correct_choice_index"] == 0
        assert {a["player_id"] for a in question["answers"]} == {
            duel.challenger.id,
            duel.opponent.id,
        }
        assert all(a["is_correct"] is True for a in question["answers"])
