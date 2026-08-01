from app.models.domain import Category
from tests.factories import make_player_client, make_questions_for_category, play_round


def test_out_of_turn_pick_rejected(duel):
    resp = duel.opponent.post(
        f"/duels/{duel.duel_id}/rounds", json={"category": Category.OLD_TESTAMENT.value}
    )
    assert resp.status_code == 409


def test_repeated_category_rejected(session, duel):
    play_round(session, duel.duel_id, duel.challenger, duel.opponent, Category.OLD_TESTAMENT)

    resp = duel.opponent.post(
        f"/duels/{duel.duel_id}/rounds", json={"category": Category.OLD_TESTAMENT.value}
    )
    assert resp.status_code == 409


def test_skipped_question_position_rejected(session, duel):
    make_questions_for_category(session, Category.OLD_TESTAMENT, 3)
    pick_resp = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds", json={"category": Category.OLD_TESTAMENT.value}
    )
    round_id = pick_resp.json()["round_id"]

    resp = duel.challenger.get(f"/duels/{duel.duel_id}/rounds/{round_id}/questions/2")
    assert resp.status_code == 409


def test_second_responder_cannot_answer_before_first(session, duel):
    make_questions_for_category(session, Category.OLD_TESTAMENT, 3)
    pick_resp = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds", json={"category": Category.OLD_TESTAMENT.value}
    )
    round_id = pick_resp.json()["round_id"]

    resp = duel.opponent.get(f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1")
    assert resp.status_code == 409


def test_double_submission_rejected(session, duel):
    make_questions_for_category(session, Category.OLD_TESTAMENT, 3)
    pick_resp = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds", json={"category": Category.OLD_TESTAMENT.value}
    )
    round_id = pick_resp.json()["round_id"]

    duel.challenger.get(f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1")
    first = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1/answer",
        json={"selected_choice_index": 0},
    )
    assert first.status_code == 200

    second = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1/answer",
        json={"selected_choice_index": 0},
    )
    assert second.status_code == 409


def test_player_not_in_duel_rejected(client, session, duel):
    outsider = make_player_client(session, client, "Outsider", "outsider@example.com")
    resp = outsider.get(f"/duels/{duel.duel_id}/state")
    assert resp.status_code == 403


def test_create_duel_rejects_self_challenge(duel):
    resp = duel.challenger.post("/duels", json={"opponent_id": duel.challenger.id})
    assert resp.status_code == 400


def test_create_duel_rejects_unknown_opponent(duel):
    resp = duel.challenger.post("/duels", json={"opponent_id": 999_999})
    assert resp.status_code == 404


def test_create_duel_requires_exactly_one_target(duel):
    both = duel.challenger.post(
        "/duels", json={"opponent_id": duel.opponent.id, "opponent_email": "opponent@example.com"}
    )
    assert both.status_code == 422

    neither = duel.challenger.post("/duels", json={})
    assert neither.status_code == 422
