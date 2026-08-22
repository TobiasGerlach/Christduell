from app.models.domain import Category
from tests.factories import make_player_client, make_questions_for_category


def start_duel(session, client):
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    bernd = make_player_client(session, client, "Bernd", "bernd@example.com")
    duel = anna.post("/duels", json={"opponent_id": bernd.id})
    assert duel.status_code == 201, duel.text
    return anna, bernd, duel.json()["id"]


def answer(actor, duel_id, round_id, position, choice):
    shown = actor.get(f"/duels/{duel_id}/rounds/{round_id}/questions/{position}")
    assert shown.status_code == 200, shown.text
    result = actor.post(
        f"/duels/{duel_id}/rounds/{round_id}/questions/{position}/answer",
        json={"selected_choice_index": choice},
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_first_responder_sees_no_opponent_answer(client, session):
    anna, bernd, duel_id = start_duel(session, client)
    make_questions_for_category(session, Category.OLD_TESTAMENT, 3)
    round_id = anna.post(
        f"/duels/{duel_id}/rounds", json={"category": Category.OLD_TESTAMENT.value}
    ).json()["round_id"]

    result = answer(anna, duel_id, round_id, 1, 0)
    assert result["opponent_choice_index"] is None
    assert result["opponent_is_timeout"] is None


def test_second_responder_sees_opponent_choice(client, session):
    anna, bernd, duel_id = start_duel(session, client)
    make_questions_for_category(session, Category.OLD_TESTAMENT, 3)
    round_id = anna.post(
        f"/duels/{duel_id}/rounds", json={"category": Category.OLD_TESTAMENT.value}
    ).json()["round_id"]

    # Anna (first responder) answers all three: picks 0, 2, then times out.
    answer(anna, duel_id, round_id, 1, 0)
    answer(anna, duel_id, round_id, 2, 2)
    answer(anna, duel_id, round_id, 3, None)

    # Bernd answers afterwards and sees Anna's picks, including the timeout.
    r1 = answer(bernd, duel_id, round_id, 1, 1)
    assert r1["opponent_choice_index"] == 0
    assert r1["opponent_is_timeout"] is False

    r2 = answer(bernd, duel_id, round_id, 2, 0)
    assert r2["opponent_choice_index"] == 2

    r3 = answer(bernd, duel_id, round_id, 3, 0)
    assert r3["opponent_choice_index"] is None
    assert r3["opponent_is_timeout"] is True
