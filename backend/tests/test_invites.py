from app.models.domain import Duel, DuelStatus
from tests.factories import make_player, make_player_client


def test_challenge_by_email(client, session):
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    make_player(session, "Bernd", "bernd@example.com")

    resp = anna.post("/duels", json={"opponent_email": "BERND@example.com"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["opponent_display_name"] == "Bernd"
    assert resp.json()["challenger_id"] == anna.id


def test_challenge_by_unknown_email_is_404(client, session):
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    resp = anna.post("/duels", json={"opponent_email": "niemand@example.com"})
    assert resp.status_code == 404


def test_challenger_is_always_the_authenticated_player(client, session):
    """A client cannot start a duel on someone else's behalf."""
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    bernd = make_player(session, "Bernd", "bernd@example.com")

    resp = anna.post("/duels", json={"opponent_id": bernd.id, "challenger_id": bernd.id})
    assert resp.status_code == 201
    assert resp.json()["challenger_id"] == anna.id


def test_search_finds_players_by_display_name_prefix(client, session):
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    make_player(session, "Bernd", "bernd@example.com")
    make_player(session, "Berta", "berta@example.com")

    results = anna.get("/players/search", params={"q": "ber"}).json()
    assert {r["display_name"] for r in results} == {"Bernd", "Berta"}
    # Search results never leak email addresses.
    assert all("email" not in r for r in results)


def test_search_matches_email_only_exactly(client, session):
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    make_player(session, "Bernd", "bernd@example.com")

    exact = anna.get("/players/search", params={"q": "bernd@example.com"}).json()
    assert [r["display_name"] for r in exact] == ["Bernd"]

    # A prefix of an address must not match, or the endpoint becomes an
    # email-harvesting tool.
    partial = anna.get("/players/search", params={"q": "bernd@exam"}).json()
    assert partial == []


def test_search_excludes_self_and_deleted_players(client, session):
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    gone = make_player_client(session, client, "Annegret", "annegret@example.com")
    gone.delete("/auth/me")

    results = anna.get("/players/search", params={"q": "ann"}).json()
    assert results == []


def test_search_requires_a_minimum_length(client, session):
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    assert anna.get("/players/search", params={"q": "a"}).status_code == 422


def test_random_duel_prefers_similarly_rated_opponents(client, session):
    """The opponent is drawn from the five closest ratings, not the whole pool."""
    anna = make_player_client(session, client, "Anna", "anna@example.com", rating=1000)
    near_ids = {
        make_player(session, f"Nah {i}", f"nah{i}@example.com", rating=1000 + i * 10).id
        for i in range(5)
    }
    for i in range(5):
        make_player(session, f"Weit {i}", f"weit{i}@example.com", rating=1900 + i * 10)

    resp = anna.post("/duels/random")
    assert resp.status_code == 201, resp.text
    assert resp.json()["opponent_id"] in near_ids


def test_random_duel_without_available_opponents_is_409(client, session):
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    assert anna.post("/duels/random").status_code == 409


def test_random_duel_skips_opponents_with_a_running_duel(client, session):
    anna = make_player_client(session, client, "Anna", "anna@example.com", rating=1000)
    busy = make_player(session, "Busy", "busy@example.com", rating=1000)
    free = make_player(session, "Free", "free@example.com", rating=1500)

    session.add(Duel(challenger_id=anna.id, opponent_id=busy.id, status=DuelStatus.ACTIVE))
    session.commit()

    resp = anna.post("/duels/random")
    assert resp.json()["opponent_id"] == free.id


def test_opponent_can_decline_a_pending_challenge(duel):
    resp = duel.opponent.post(f"/duels/{duel.duel_id}/decline")
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"

    # A declined duel disappears from both players' lists...
    assert duel.opponent.get("/duels").json() == []
    assert duel.challenger.get("/duels").json() == []
    # ...and can no longer be played.
    played = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds", json={"category": "old_testament"}
    )
    assert played.status_code == 409


def test_challenger_cannot_decline_their_own_challenge(duel):
    assert duel.challenger.post(f"/duels/{duel.duel_id}/decline").status_code == 403


def test_declining_a_running_duel_is_rejected(session, duel):
    from app.models.domain import Category
    from tests.factories import make_questions_for_category

    make_questions_for_category(session, Category.HISTORY, 3)
    duel.challenger.post(f"/duels/{duel.duel_id}/rounds", json={"category": "history"})

    assert duel.opponent.post(f"/duels/{duel.duel_id}/decline").status_code == 409
