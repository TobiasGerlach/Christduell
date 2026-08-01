from app.models.domain import Category
from tests.factories import make_questions_for_category, play_round


def test_scores_count_only_correct_answers(session, duel):
    play_round(
        session,
        duel.duel_id,
        duel.challenger,
        duel.opponent,
        Category.OLD_TESTAMENT,
        picker_choices=(0, 1, 0),  # 2 correct (question's correct index is always 0)
        responder_choices=(0, 0, 1),  # 2 correct
    )

    summaries = duel.challenger.get("/duels").json()
    item = next(d for d in summaries if d["id"] == duel.duel_id)
    assert item["challenger_score"] == 2
    assert item["opponent_score"] == 2

    state = duel.challenger.get(f"/duels/{duel.duel_id}/state").json()
    assert state["challenger_score"] == 2
    assert state["opponent_score"] == 2


def test_correctness_is_computed_server_side_from_question_answer_key(session, duel):
    make_questions_for_category(session, Category.NEW_TESTAMENT, 3)
    pick_resp = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds", json={"category": Category.NEW_TESTAMENT.value}
    )
    round_id = pick_resp.json()["round_id"]

    duel.challenger.get(f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1")
    correct = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1/answer",
        json={"selected_choice_index": 0},
    ).json()
    assert correct["is_correct"] is True
    assert correct["correct_choice_index"] == 0

    duel.challenger.get(f"/duels/{duel.duel_id}/rounds/{round_id}/questions/2")
    wrong = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/2/answer",
        json={"selected_choice_index": 3},
    ).json()
    assert wrong["is_correct"] is False
    assert wrong["correct_choice_index"] == 0


def test_duel_summary_includes_both_display_names(duel):
    summaries = duel.challenger.get("/duels").json()
    item = next(d for d in summaries if d["id"] == duel.duel_id)
    assert item["challenger_display_name"] == "Challenger"
    assert item["opponent_display_name"] == "Opponent"
