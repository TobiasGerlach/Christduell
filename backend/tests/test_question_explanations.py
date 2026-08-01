"""A revealed answer carries its source; an unrevealed one gives nothing away."""

from app.models.domain import Category
from tests.factories import answer_all_questions, make_question


def _round_with_sourced_question(session, duel) -> int:
    for index in range(3):
        make_question(
            session,
            Category.HISTORY,
            prompt=f"Frage {index}",
            reference="Gen 6,14",
            explanation="Noah baute die Arche aus Tannenholz.",
        )
    pick = duel.challenger.post(f"/duels/{duel.duel_id}/rounds", json={"category": "history"})
    assert pick.status_code == 201, pick.text
    return pick.json()["round_id"]


def test_answering_returns_the_reference_and_explanation(session, duel):
    round_id = _round_with_sourced_question(session, duel)

    duel.challenger.get(f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1")
    result = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1/answer",
        json={"selected_choice_index": 0},
    ).json()

    assert result["reference"] == "Gen 6,14"
    assert result["explanation"] == "Noah baute die Arche aus Tannenholz."


def test_history_withholds_the_source_until_the_round_reveals(session, duel):
    round_id = _round_with_sourced_question(session, duel)
    answer_all_questions(duel.challenger, duel.duel_id, round_id)

    # The opponent still has to play this round — handing them the explanation
    # would hand them the answer.
    before = duel.opponent.get(f"/duels/{duel.duel_id}/history").json()
    for question in before["rounds"][0]["questions"]:
        assert question["reference"] is None
        assert question["explanation"] is None

    answer_all_questions(duel.opponent, duel.duel_id, round_id)

    after = duel.opponent.get(f"/duels/{duel.duel_id}/history").json()
    for question in after["rounds"][0]["questions"]:
        assert question["reference"] == "Gen 6,14"
        assert question["explanation"] == "Noah baute die Arche aus Tannenholz."


def test_questions_without_a_source_still_work(session, duel):
    """Sourcing is optional — a bare question must not break the reveal."""
    for index in range(3):
        make_question(session, Category.PSALMS_PRAYERS, prompt=f"Ohne Quelle {index}")
    round_id = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds", json={"category": "psalms_prayers"}
    ).json()["round_id"]

    duel.challenger.get(f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1")
    result = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1/answer",
        json={"selected_choice_index": 0},
    ).json()

    assert result["reference"] is None
    assert result["is_correct"] is True
