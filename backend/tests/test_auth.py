import pytest

from app.core.security import create_access_token, decode_access_token
from app.models.domain import Player, ResearchConsent
from tests.factories import DEFAULT_PASSWORD, make_player, make_player_client

REGISTRATION = {
    "display_name": "Neuer Spieler",
    "email": "neu@example.com",
    "password": "ein-gutes-passwort",
    "min_age_confirmed": True,
}


def test_register_returns_token_and_account(client):
    resp = client.post("/auth/register", json=REGISTRATION)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"]) == body["player"]["id"]
    assert body["player"]["display_name"] == "Neuer Spieler"
    assert body["player"]["subscription_tier"] == "research"
    assert body["player"]["subscription_active"] is False


def test_registered_password_is_hashed_not_stored(client, session):
    resp = client.post("/auth/register", json=REGISTRATION)
    player = session.get(Player, resp.json()["player"]["id"])
    assert player.password_hash != REGISTRATION["password"]
    assert REGISTRATION["password"] not in player.password_hash


def test_register_rejects_duplicate_email_case_insensitively(client):
    assert client.post("/auth/register", json=REGISTRATION).status_code == 201
    duplicate = client.post(
        "/auth/register", json={**REGISTRATION, "email": "NEU@example.com"}
    )
    assert duplicate.status_code == 409


def test_register_rejects_short_password(client):
    resp = client.post("/auth/register", json={**REGISTRATION, "password": "kurz"})
    assert resp.status_code == 422


def test_register_rejects_malformed_email(client):
    resp = client.post("/auth/register", json={**REGISTRATION, "email": "not-an-email"})
    assert resp.status_code == 422


def test_login_succeeds_with_correct_password(client, session):
    make_player(session, "Anna", "anna@example.com")
    resp = client.post(
        "/auth/login", json={"email": "anna@example.com", "password": DEFAULT_PASSWORD}
    )
    assert resp.status_code == 200
    assert resp.json()["player"]["display_name"] == "Anna"


def test_login_rejects_wrong_password(client, session):
    make_player(session, "Anna", "anna@example.com")
    resp = client.post("/auth/login", json={"email": "anna@example.com", "password": "falsch"})
    assert resp.status_code == 401


def test_login_does_not_reveal_whether_an_account_exists(client, session):
    make_player(session, "Anna", "anna@example.com")
    wrong_password = client.post(
        "/auth/login", json={"email": "anna@example.com", "password": "falsch"}
    )
    unknown_account = client.post(
        "/auth/login", json={"email": "niemand@example.com", "password": "falsch"}
    )
    assert wrong_password.status_code == unknown_account.status_code == 401
    assert wrong_password.json() == unknown_account.json()


def test_me_returns_the_token_owner(client, session):
    player = make_player_client(session, client, "Anna", "anna@example.com")
    resp = player.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["id"] == player.id


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer not-a-token"},
        {"Authorization": "Basic anna@example.com"},
    ],
)
def test_me_rejects_missing_or_broken_credentials(client, headers):
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_token_for_deleted_player_is_rejected(client, session):
    player = make_player_client(session, client, "Anna", "anna@example.com")
    assert player.delete("/auth/me").status_code == 204
    assert player.get("/auth/me").status_code == 401


def test_token_for_nonexistent_player_is_rejected(client):
    token = create_access_token(999_999)
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_change_password_invalidates_the_old_one(client, session):
    player = make_player_client(session, client, "Anna", "anna@example.com")
    changed = player.post(
        "/auth/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "neues-passwort-1"},
    )
    assert changed.status_code == 204

    old = client.post(
        "/auth/login", json={"email": "anna@example.com", "password": DEFAULT_PASSWORD}
    )
    assert old.status_code == 401
    new = client.post(
        "/auth/login", json={"email": "anna@example.com", "password": "neues-passwort-1"}
    )
    assert new.status_code == 200


def test_change_password_requires_the_current_one(client, session):
    player = make_player_client(session, client, "Anna", "anna@example.com")
    resp = player.post(
        "/auth/change-password",
        json={"current_password": "falsch", "new_password": "neues-passwort-1"},
    )
    assert resp.status_code == 401


def test_update_display_name(client, session):
    player = make_player_client(session, client, "Anna", "anna@example.com")
    resp = player.patch("/auth/me", json={"display_name": "Anna B."})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Anna B."


def test_account_deletion_scrubs_personal_data_and_blocks_login(client, session):
    player = make_player_client(session, client, "Anna", "anna@example.com")
    session.add(ResearchConsent(player_id=player.id))
    session.commit()

    assert player.delete("/auth/me").status_code == 204

    session.expire_all()
    deleted = session.get(Player, player.id)
    assert deleted.deleted_at is not None
    assert deleted.display_name == "Gelöschter Spieler"
    assert "anna@example.com" not in deleted.email
    assert deleted.password_hash is None
    assert deleted.push_token is None
    # Research participation ends with the account.
    assert session.get(ResearchConsent, player.id).withdrawn_at is not None

    assert (
        client.post(
            "/auth/login", json={"email": "anna@example.com", "password": DEFAULT_PASSWORD}
        ).status_code
        == 401
    )


def test_registration_rejects_reserved_tld_addresses(client):
    """A regression guard: the demo accounts were once seeded on a .test domain
    and therefore could not be logged into at all."""
    resp = client.post(
        "/auth/register",
        json={
            "display_name": "Test",
            "email": "someone@christduell.test",
            "password": "password-1234",
            "min_age_confirmed": True,
        },
    )
    assert resp.status_code == 422


def test_duplicate_registration_that_races_past_the_check_is_a_conflict(client, session):
    """The unique index is the real guard; it must surface as 409, not a 500."""
    make_player(session, "Erste", "race@example.com")

    resp = client.post(
        "/auth/register",
        json={**REGISTRATION, "display_name": "Zweite", "email": "race@example.com"},
    )
    assert resp.status_code == 409


def test_registration_requires_the_age_confirmation(client, session):
    """GDPR Art. 8: consent age 16 in Germany; younger players need parental
    consent, which the checkbox wording covers."""
    resp = client.post("/auth/register", json={**REGISTRATION, "min_age_confirmed": False})
    assert resp.status_code == 400
    assert "16" in resp.json()["detail"]


def test_registration_records_when_the_age_was_confirmed(client, session):
    resp = client.post("/auth/register", json=REGISTRATION)
    player = session.get(Player, resp.json()["player"]["id"])
    assert player.min_age_confirmed_at is not None
