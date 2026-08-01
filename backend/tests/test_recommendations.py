from app.models.domain import Category
from tests.factories import play_round


def test_recommendations_returns_three_distinct_categories(duel):
    resp = duel.challenger.get(f"/duels/{duel.duel_id}/recommendations")
    assert resp.status_code == 200
    recommendations = resp.json()
    assert len(recommendations) == 3
    assert len({r["category"] for r in recommendations}) == 3
    for rec in recommendations:
        assert rec["display_name"]  # German display name present


def test_recommendations_rejects_when_not_pickers_turn(duel):
    resp = duel.opponent.get(f"/duels/{duel.duel_id}/recommendations")
    assert resp.status_code == 409


def test_recommendations_excludes_categories_already_used(session, duel):
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
