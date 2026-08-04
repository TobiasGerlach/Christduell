"""Login and registration must not be free to brute-force.

Login is limited per account (a shared church wifi must not lock a whole group
out); registration per IP (slows mass account creation). In-memory and
process-local — correct for the single-instance deployment.
"""

import pytest

from app.core import ratelimit
from tests.factories import DEFAULT_PASSWORD, make_player

REGISTRATION = {
    "display_name": "Neu",
    "password": "ein-gutes-passwort",
    "min_age_confirmed": True,
}


@pytest.fixture(autouse=True)
def _fresh_limits():
    """Rate-limit state is module-level and would otherwise leak across tests."""
    ratelimit.limiter.reset()
    yield
    ratelimit.limiter.reset()


def _fail_login(client, email: str):
    return client.post("/auth/login", json={"email": email, "password": "falsch"})


def test_repeated_login_failures_are_blocked(client, session, settings_override):
    settings_override(login_rate_limit_attempts=3)
    make_player(session, "Anna", "anna@example.com")

    for _ in range(3):
        assert _fail_login(client, "anna@example.com").status_code == 401

    blocked = client.post(
        "/auth/login", json={"email": "anna@example.com", "password": DEFAULT_PASSWORD}
    )
    # Even the correct password is refused once the account is being hammered.
    assert blocked.status_code == 429


def test_the_limit_is_per_account_not_global(client, session, settings_override):
    """Thirty youths behind one NAT must not lock each other out."""
    settings_override(login_rate_limit_attempts=3)
    make_player(session, "Anna", "anna@example.com")
    make_player(session, "Bernd", "bernd@example.com")

    for _ in range(3):
        _fail_login(client, "anna@example.com")

    ok = client.post(
        "/auth/login", json={"email": "bernd@example.com", "password": DEFAULT_PASSWORD}
    )
    assert ok.status_code == 200


def test_a_successful_login_clears_the_counter(client, session, settings_override):
    settings_override(login_rate_limit_attempts=3)
    make_player(session, "Anna", "anna@example.com")

    for _ in range(2):
        _fail_login(client, "anna@example.com")
    assert (
        client.post(
            "/auth/login", json={"email": "anna@example.com", "password": DEFAULT_PASSWORD}
        ).status_code
        == 200
    )

    # The slate is clean again — two more failures don't add up to the old two.
    for _ in range(2):
        assert _fail_login(client, "anna@example.com").status_code == 401


def test_unknown_addresses_are_rate_limited_too(client, settings_override):
    """Guessing addresses must not be cheaper than guessing passwords."""
    settings_override(login_rate_limit_attempts=3)
    for _ in range(3):
        assert _fail_login(client, "niemand@example.com").status_code == 401
    assert _fail_login(client, "niemand@example.com").status_code == 429


def test_mass_registration_from_one_address_is_blocked(client, settings_override):
    settings_override(register_rate_limit_attempts=2)

    for index in range(2):
        resp = client.post(
            "/auth/register", json={**REGISTRATION, "email": f"p{index}@example.com"}
        )
        assert resp.status_code == 201

    third = client.post("/auth/register", json={**REGISTRATION, "email": "p9@example.com"})
    assert third.status_code == 429
