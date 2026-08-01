"""Every player-scoped endpoint must reject unauthenticated calls.

Before tokens existed these endpoints took a `player_id` parameter and trusted
it, so this file is the regression guard: any new route that reads or writes a
player's data belongs in this list.
"""

import pytest

PROTECTED_ENDPOINTS = [
    ("get", "/auth/me"),
    ("patch", "/auth/me"),
    ("delete", "/auth/me"),
    ("post", "/auth/change-password"),
    ("get", "/billing/status"),
    ("post", "/billing/checkout"),
    ("post", "/billing/cancel"),
    ("get", "/duels"),
    ("post", "/duels"),
    ("post", "/duels/random"),
    ("post", "/duels/1/decline"),
    ("get", "/duels/1/state"),
    ("get", "/duels/1/recommendations"),
    ("post", "/duels/1/rounds"),
    ("get", "/duels/1/rounds/1/questions/1"),
    ("post", "/duels/1/rounds/1/questions/1/answer"),
    ("get", "/duels/1/history"),
    ("post", "/notifications/register-token"),
    ("delete", "/notifications/register-token"),
    ("post", "/questions/1/report"),
    ("get", "/players/search?q=abc"),
    ("get", "/players/1"),
    ("get", "/research/consent"),
    ("post", "/research/consent"),
    ("delete", "/research/consent"),
    ("get", "/research/questionnaire/current"),
    ("post", "/research/questionnaire/faith_background/answers"),
]


@pytest.mark.parametrize(("method", "path"), PROTECTED_ENDPOINTS)
def test_endpoint_requires_authentication(client, method, path):
    response = client.request(method, path, json={})
    assert response.status_code == 401, f"{method.upper()} {path} returned {response.status_code}"


def test_health_endpoint_stays_public(client):
    assert client.get("/health").status_code == 200
