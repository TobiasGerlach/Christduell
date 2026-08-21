from app.core.security import create_password_reset_token
from app.services import email as email_service
from tests.factories import make_player


def sent_emails(monkeypatch):
    outbox = []
    monkeypatch.setattr(
        email_service._executor, "submit", lambda fn, *args: outbox.append(args)
    )
    return outbox


def enable_email(settings_override):
    settings_override(smtp_host="smtp.example.com", smtp_from="app@example.com")


# ---------------------------------------------------------------------------
# forgot-password
# ---------------------------------------------------------------------------


def test_forgot_password_sends_reset_link(client, session, settings_override, monkeypatch):
    enable_email(settings_override)
    outbox = sent_emails(monkeypatch)
    make_player(session, "Anna", "anna@example.com")

    response = client.post("/auth/forgot-password", json={"email": "anna@example.com"})
    assert response.status_code == 204
    assert len(outbox) == 1
    to, subject, body = outbox[0]
    assert to == "anna@example.com"
    assert "/passwort-zuruecksetzen?token=" in body


def test_forgot_password_is_silent_for_unknown_email(
    client, settings_override, monkeypatch
):
    enable_email(settings_override)
    outbox = sent_emails(monkeypatch)
    response = client.post("/auth/forgot-password", json={"email": "wer@example.com"})
    assert response.status_code == 204
    assert outbox == []


# ---------------------------------------------------------------------------
# reset-password
# ---------------------------------------------------------------------------


def test_reset_password_with_valid_token(client, session):
    player = make_player(session, "Anna", "anna@example.com")
    token = create_password_reset_token(player.id, player.password_hash)

    response = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "neues-passwort-1"}
    )
    assert response.status_code == 204

    login = client.post(
        "/auth/login", json={"email": "anna@example.com", "password": "neues-passwort-1"}
    )
    assert login.status_code == 200


def test_reset_token_is_single_use(client, session):
    player = make_player(session, "Anna", "anna@example.com")
    token = create_password_reset_token(player.id, player.password_hash)

    first = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "neues-passwort-1"}
    )
    assert first.status_code == 204
    second = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "anderes-passwort-2"}
    )
    assert second.status_code == 400


def test_reset_rejects_garbage_token(client):
    response = client.post(
        "/auth/reset-password", json={"token": "kaputt", "new_password": "neues-passwort-1"}
    )
    assert response.status_code == 400


def test_reset_rejects_access_token(client, session):
    """A normal login token must not work as a reset token."""
    from app.core.security import create_access_token

    player = make_player(session, "Anna", "anna@example.com")
    token = create_access_token(player.id)
    response = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "neues-passwort-1"}
    )
    assert response.status_code == 400


def test_reset_rejects_short_password(client, session):
    player = make_player(session, "Anna", "anna@example.com")
    token = create_password_reset_token(player.id, player.password_hash)
    response = client.post("/auth/reset-password", json={"token": token, "new_password": "kurz"})
    assert response.status_code == 422
