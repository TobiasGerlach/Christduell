from app.models.domain import Category
from tests.factories import make_player, make_questions_for_category

CATEGORIES = list(Category)[:8]


def test_full_duel_alternates_pickers_and_finishes(client, session):
    challenger = make_player(session, "Challenger", "challenger@test.local")
    opponent = make_player(session, "Opponent", "opponent@test.local")

    create_resp = client.post(
        "/duels", json={"challenger_id": challenger.id, "opponent_id": opponent.id}
    )
    assert create_resp.status_code == 201
    duel_id = create_resp.json()["id"]

    pickers: list[int] = []
    for sequence in range(1, 9):
        state = client.get(f"/duels/{duel_id}/state", params={"player_id": challenger.id}).json()
        assert state["action"] == "pick_category"
        assert state["round_sequence"] == sequence
        picker_id = state["acting_player_id"]
        responder_id = opponent.id if picker_id == challenger.id else challenger.id
        pickers.append(picker_id)

        category = CATEGORIES[sequence - 1]
        make_questions_for_category(session, category, 3)

        pick_resp = client.post(
            f"/duels/{duel_id}/rounds",
            json={"player_id": picker_id, "category": category.value},
        )
        assert pick_resp.status_code == 201, pick_resp.text
        pick_state = pick_resp.json()
        assert pick_state["action"] == "answer_question"
        assert pick_state["acting_player_id"] == picker_id
        round_id = pick_state["round_id"]

        for actor in (picker_id, responder_id):
            for position in (1, 2, 3):
                get_resp = client.get(
                    f"/duels/{duel_id}/rounds/{round_id}/questions/{position}",
                    params={"player_id": actor},
                )
                assert get_resp.status_code == 200, get_resp.text
                answer_resp = client.post(
                    f"/duels/{duel_id}/rounds/{round_id}/questions/{position}/answer",
                    json={"player_id": actor, "selected_choice_index": 0},
                )
                assert answer_resp.status_code == 200, answer_resp.text
                result = answer_resp.json()
                assert result["round_revealed"] == (actor == responder_id and position == 3)
                assert result["duel_finished"] == (
                    actor == responder_id and position == 3 and sequence == 8
                )

    # Whoever answers second in a round picks the next one — over 8 rounds that
    # alternation means each player picks exactly half the categories.
    assert pickers.count(challenger.id) == 4
    assert pickers.count(opponent.id) == 4
    assert len(set(pickers[i] for i in range(0, 8, 2))) == 1  # picker alternates strictly

    final_state = client.get(f"/duels/{duel_id}/state", params={"player_id": challenger.id}).json()
    assert final_state["action"] == "finished"
    assert final_state["acting_player_id"] is None

    summaries = client.get("/duels", params={"player_id": challenger.id}).json()
    finished = next(d for d in summaries if d["id"] == duel_id)
    assert finished["status"] == "finished"
    assert finished["finished_at"] is not None
    # Every answer in this test selects choice 0, which factories always mark
    # correct — so both players run the table on all 24 questions.
    assert finished["challenger_score"] == 24
    assert finished["opponent_score"] == 24
