from app.models.domain import Category
from tests.factories import make_questions_for_category

CATEGORIES = list(Category)[:8]


def test_full_duel_alternates_pickers_and_finishes(session, duel):
    duel_id = duel.duel_id
    by_id = {duel.challenger.id: duel.challenger, duel.opponent.id: duel.opponent}

    pickers: list[int] = []
    for sequence in range(1, 9):
        state = duel.challenger.get(f"/duels/{duel_id}/state").json()
        assert state["action"] == "pick_category"
        assert state["round_sequence"] == sequence
        picker = by_id[state["acting_player_id"]]
        responder = by_id[state["waiting_player_id"]]
        pickers.append(picker.id)

        category = CATEGORIES[sequence - 1]
        make_questions_for_category(session, category, 3)

        pick_resp = picker.post(f"/duels/{duel_id}/rounds", json={"category": category.value})
        assert pick_resp.status_code == 201, pick_resp.text
        pick_state = pick_resp.json()
        assert pick_state["action"] == "answer_question"
        assert pick_state["acting_player_id"] == picker.id
        round_id = pick_state["round_id"]

        for actor in (picker, responder):
            for position in (1, 2, 3):
                get_resp = actor.get(f"/duels/{duel_id}/rounds/{round_id}/questions/{position}")
                assert get_resp.status_code == 200, get_resp.text
                answer_resp = actor.post(
                    f"/duels/{duel_id}/rounds/{round_id}/questions/{position}/answer",
                    json={"selected_choice_index": 0},
                )
                assert answer_resp.status_code == 200, answer_resp.text
                result = answer_resp.json()
                assert result["round_revealed"] == (actor is responder and position == 3)
                assert result["duel_finished"] == (
                    actor is responder and position == 3 and sequence == 8
                )

    # Whoever answers second in a round picks the next one — over 8 rounds that
    # alternation means each player picks exactly half the categories.
    assert pickers.count(duel.challenger.id) == 4
    assert pickers.count(duel.opponent.id) == 4
    assert len({pickers[i] for i in range(0, 8, 2)}) == 1  # picker alternates strictly

    final_state = duel.challenger.get(f"/duels/{duel_id}/state").json()
    assert final_state["action"] == "finished"
    assert final_state["acting_player_id"] is None

    summaries = duel.challenger.get("/duels").json()
    finished = next(d for d in summaries if d["id"] == duel_id)
    assert finished["status"] == "finished"
    assert finished["finished_at"] is not None
    # Every answer in this test selects choice 0, which factories always mark
    # correct — so both players run the table on all 24 questions.
    assert finished["challenger_score"] == 24
    assert finished["opponent_score"] == 24
