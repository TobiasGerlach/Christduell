import pytest

from app.core.time import utcnow
from app.models.domain import Category, Question
from tests.factories import make_questions_for_category, play_round


@pytest.fixture(name="stocked")
def stocked_fixture(session):
    """Three questions in every category — the state a seeded database is in."""
    for category in Category:
        make_questions_for_category(session, category, 3)


def test_recommendations_returns_three_distinct_categories(duel, stocked):
    resp = duel.challenger.get(f"/duels/{duel.duel_id}/recommendations")
    assert resp.status_code == 200
    recommendations = resp.json()
    assert len(recommendations) == 3
    assert len({r["category"] for r in recommendations}) == 3
    for rec in recommendations:
        assert rec["display_name"]  # German display name present


def test_recommendations_rejects_when_not_pickers_turn(duel, stocked):
    resp = duel.opponent.get(f"/duels/{duel.duel_id}/recommendations")
    assert resp.status_code == 409


def test_recommendations_excludes_categories_already_used(session, duel, stocked):
    used_categories = list(Category)[:7]
    picker, responder = duel.challenger, duel.opponent
    for category in used_categories:
        play_round(session, duel.duel_id, picker, responder, category)
        picker, responder = responder, picker

    state = duel.challenger.get(f"/duels/{duel.duel_id}/state").json()
    acting = picker if state["acting_player_id"] == picker.id else responder

    recommendations = acting.get(f"/duels/{duel.duel_id}/recommendations").json()
    assert len(recommendations) == 3
    used_values = {c.value for c in used_categories}
    assert all(rec["category"] not in used_values for rec in recommendations)


# ---------------------------------------------------------------------------
# Categories can run dry, because reported questions retire themselves
# ---------------------------------------------------------------------------


def retire_category(session, category: Category) -> None:
    for question in session.exec(  # type: ignore[call-overload]
        __import__("sqlmodel").select(Question).where(Question.category == category)
    ):
        question.retired_at = utcnow()
        session.add(question)
    session.commit()


def test_recommendations_skip_categories_without_enough_questions(session, duel, stocked):
    """A category emptied by reports must never be offered — tapping it would fail."""
    starved = list(Category)[:4]
    for category in starved:
        retire_category(session, category)

    recommendations = duel.challenger.get(f"/duels/{duel.duel_id}/recommendations").json()
    assert not {r["category"] for r in recommendations} & {c.value for c in starved}


def test_recommendations_report_when_no_category_can_be_played(session, duel, stocked):
    for category in Category:
        retire_category(session, category)

    resp = duel.challenger.get(f"/duels/{duel.duel_id}/recommendations")
    assert resp.status_code == 409
    assert "nicht genug Fragen" in resp.json()["detail"]


def test_picking_a_starved_category_is_a_conflict_not_a_crash(session, duel, stocked):
    retire_category(session, Category.HISTORY)

    resp = duel.challenger.post(f"/duels/{duel.duel_id}/rounds", json={"category": "history"})
    assert resp.status_code == 409, resp.text
    assert "nicht genug Fragen" in resp.json()["detail"]


def test_a_starved_category_leaves_the_duel_playable(session, duel, stocked):
    """The failed pick must not have created a half-built round."""
    retire_category(session, Category.HISTORY)
    duel.challenger.post(f"/duels/{duel.duel_id}/rounds", json={"category": "history"})

    state = duel.challenger.get(f"/duels/{duel.duel_id}/state").json()
    assert state["action"] == "pick_category"
    assert state["round_sequence"] == 1

    ok = duel.challenger.post(f"/duels/{duel.duel_id}/rounds", json={"category": "psalms_prayers"})
    assert ok.status_code == 201
