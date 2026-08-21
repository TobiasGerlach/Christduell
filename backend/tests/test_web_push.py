from sqlmodel import select

from app.models.domain import WebPushSubscription
from app.services import web_push
from tests.factories import make_player_client

SUBSCRIPTION = {
    "endpoint": "https://push.example.com/sub/abc123",
    "keys": {"p256dh": "p256dh-key", "auth": "auth-secret"},
}


# ---------------------------------------------------------------------------
# Public key
# ---------------------------------------------------------------------------


def test_public_key_404_when_unconfigured(client):
    response = client.get("/notifications/web-push/public-key")
    assert response.status_code == 404


def test_public_key_served_when_configured(client, settings_override):
    settings_override(vapid_public_key="public-key", vapid_private_key="private-key")
    response = client.get("/notifications/web-push/public-key")
    assert response.status_code == 200
    assert response.json() == {"public_key": "public-key"}


# ---------------------------------------------------------------------------
# Subscribe / unsubscribe
# ---------------------------------------------------------------------------


def test_subscribe_requires_auth(client):
    response = client.post("/notifications/web-push/subscriptions", json=SUBSCRIPTION)
    assert response.status_code == 401


def test_subscribe_stores_subscription(client, session):
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    response = anna.post("/notifications/web-push/subscriptions", json=SUBSCRIPTION)
    assert response.status_code == 204

    stored = session.exec(select(WebPushSubscription)).one()
    assert stored.player_id == anna.player.id
    assert stored.endpoint == SUBSCRIPTION["endpoint"]
    assert stored.p256dh == "p256dh-key"
    assert stored.auth == "auth-secret"


def test_subscribe_is_idempotent_per_endpoint(client, session):
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    anna.post("/notifications/web-push/subscriptions", json=SUBSCRIPTION)
    anna.post("/notifications/web-push/subscriptions", json=SUBSCRIPTION)
    assert len(session.exec(select(WebPushSubscription)).all()) == 1


def test_endpoint_moves_to_new_account_on_shared_browser(client, session):
    """The same browser signing into another account must not leak pushes."""
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    bernd = make_player_client(session, client, "Bernd", "bernd@example.com")

    anna.post("/notifications/web-push/subscriptions", json=SUBSCRIPTION)
    bernd.post("/notifications/web-push/subscriptions", json=SUBSCRIPTION)

    stored = session.exec(select(WebPushSubscription)).one()
    assert stored.player_id == bernd.player.id


def test_unsubscribe_deletes_own_subscription(client, session):
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    anna.post("/notifications/web-push/subscriptions", json=SUBSCRIPTION)
    response = anna.delete(
        "/notifications/web-push/subscriptions",
        params={"endpoint": SUBSCRIPTION["endpoint"]},
    )
    assert response.status_code == 204
    assert session.exec(select(WebPushSubscription)).first() is None


def test_unsubscribe_ignores_foreign_subscription(client, session):
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    bernd = make_player_client(session, client, "Bernd", "bernd@example.com")
    anna.post("/notifications/web-push/subscriptions", json=SUBSCRIPTION)

    response = bernd.delete(
        "/notifications/web-push/subscriptions",
        params={"endpoint": SUBSCRIPTION["endpoint"]},
    )
    assert response.status_code == 204
    remaining = session.exec(select(WebPushSubscription)).one()
    assert remaining.player_id == anna.player.id


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


def test_send_is_noop_without_keys(monkeypatch):
    submitted = []
    monkeypatch.setattr(web_push._executor, "submit", lambda *a: submitted.append(a))
    web_push.send_to_player(1, "t", "b")
    assert submitted == []


def test_send_queues_when_configured(settings_override, monkeypatch):
    settings_override(vapid_public_key="public-key", vapid_private_key="private-key")
    submitted = []
    monkeypatch.setattr(web_push._executor, "submit", lambda *a: submitted.append(a))
    web_push.send_to_player(1, "Du bist dran", "body", {"duelId": 7})
    assert len(submitted) == 1
