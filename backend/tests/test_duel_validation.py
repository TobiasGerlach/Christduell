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


def test_out_of_turn_pick_rejected(client, duel):
    resp = client.post(
        f"/duels/{duel.duel_id}/rounds",
        json={"player_id": duel.opponent.id, "category": Category.OLD_TESTAMENT.value},
    )
    assert resp.status_code == 409


def test_repeated_category_rejected(client, session, duel):
    play_round(client, session, duel.duel_id, duel.challenger.id, duel.opponent.id, Category.OLD_TESTAMENT)

    resp = client.post(
        f"/duels/{duel.duel_id}/rounds",
        json={"player_id": duel.opponent.id, "category": Category.OLD_TESTAMENT.value},
    )
    assert resp.status_code == 409


def test_skipped_question_position_rejected(client, session, duel):
    make_questions_for_category(session, Category.OLD_TESTAMENT, 3)
    pick_resp = client.post(
        f"/duels/{duel.duel_id}/rounds",
        json={"player_id": duel.challenger.id, "category": Category.OLD_TESTAMENT.value},
    )
    round_id = pick_resp.json()["round_id"]

    resp = client.get(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/2",
        params={"player_id": duel.challenger.id},
    )
    assert resp.status_code == 409


def test_second_responder_cannot_answer_before_first(client, session, duel):
    make_questions_for_category(session, Category.OLD_TESTAMENT, 3)
    pick_resp = client.post(
        f"/duels/{duel.duel_id}/rounds",
        json={"player_id": duel.challenger.id, "category": Category.OLD_TESTAMENT.value},
    )
    round_id = pick_resp.json()["round_id"]

    resp = client.get(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1",
        params={"player_id": duel.opponent.id},
    )
    assert resp.status_code == 409


def test_double_submission_rejected(client, session, duel):
    make_questions_for_category(session, Category.OLD_TESTAMENT, 3)
    pick_resp = client.post(
        f"/duels/{duel.duel_id}/rounds",
        json={"player_id": duel.challenger.id, "category": Category.OLD_TESTAMENT.value},
    )
    round_id = pick_resp.json()["round_id"]

    client.get(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1",
        params={"player_id": duel.challenger.id},
    )
    first = client.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1/answer",
        json={"player_id": duel.challenger.id, "selected_choice_index": 0},
    )
    assert first.status_code == 200

    second = client.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1/answer",
        json={"player_id": duel.challenger.id, "selected_choice_index": 0},
    )
    assert second.status_code == 409


def test_player_not_in_duel_rejected(client, session, duel):
    outsider = make_player(session, "Outsider", "outsider@test.local")
    resp = client.get(f"/duels/{duel.duel_id}/state", params={"player_id": outsider.id})
    assert resp.status_code == 403


def test_create_duel_rejects_self_challenge(client, session, duel):
    resp = client.post(
        "/duels", json={"challenger_id": duel.challenger.id, "opponent_id": duel.challenger.id}
    )
    assert resp.status_code == 400
