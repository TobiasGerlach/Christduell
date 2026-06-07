from types import SimpleNamespace

import pytest

from app.models.domain import Category
from tests.factories import make_player, play_round


@pytest.fixture(name="duel")
def duel_fixture(client, session):
    challenger = make_player(session, "Challenger", "challenger@test.local")
    opponent = make_player(session, "Opponent", "opponent@test.local")
    create_resp = client.post(
        "/duels", json={"challenger_id": challenger.id, "opponent_id": opponent.id}
    )
    return SimpleNamespace(duel_id=create_resp.json()["id"], challenger=challenger, opponent=opponent)


def test_recommendations_returns_three_distinct_categories(client, session, duel):
    resp = client.get(
        f"/duels/{duel.duel_id}/recommendations", params={"player_id": duel.challenger.id}
    )
    assert resp.status_code == 200
    recommendations = resp.json()
    assert len(recommendations) == 3
    assert len({r["category"] for r in recommendations}) == 3
    for rec in recommendations:
        assert rec["display_name"]  # German display name present


def test_recommendations_rejects_when_not_pickers_turn(client, session, duel):
    resp = client.get(
        f"/duels/{duel.duel_id}/recommendations", params={"player_id": duel.opponent.id}
    )
    assert resp.status_code == 409


def test_recommendations_excludes_categories_already_used(client, session, duel):
    used_categories = list(Category)[:7]
    picker, responder = duel.challenger, duel.opponent
    for category in used_categories:
        play_round(client, session, duel.duel_id, picker.id, responder.id, category)
        picker, responder = responder, picker

    state = client.get(f"/duels/{duel.duel_id}/state", params={"player_id": duel.challenger.id}).json()
    acting_player_id = state["acting_player_id"]

    resp = client.get(
        f"/duels/{duel.duel_id}/recommendations", params={"player_id": acting_player_id}
    )
    recommendations = resp.json()
    assert len(recommendations) == 3
    used_values = {c.value for c in used_categories}
    assert all(rec["category"] not in used_values for rec in recommendations)
