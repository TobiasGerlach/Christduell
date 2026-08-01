from datetime import timedelta

from app.core.time import utcnow
from app.models.domain import Player, ResearchConsent, SubscriptionTier
from app.services.billing import handle_stripe_event
from app.services.research import GAMES_REQUIRED_BEFORE_QUESTIONNAIRE, get_due_questionnaire
from app.services.subscriptions import (
    downgrade_expired_subscriptions,
    is_subscription_active,
)
from tests.factories import make_player, make_player_client
from tests.test_research import make_finished_duels

# ---------------------------------------------------------------------------
# Provider "none" — the default, so a half-configured server cannot take money
# ---------------------------------------------------------------------------


def test_status_reports_disabled_billing(client, session, settings_override):
    settings_override(billing_provider="none")
    anna = make_player_client(session, client, "Anna", "anna@example.com")

    body = anna.get("/billing/status").json()
    assert body["provider"] == "none"
    assert body["tier"] == "research"
    assert body["active"] is False


def test_checkout_unavailable_without_a_provider(client, session, settings_override):
    settings_override(billing_provider="none")
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    assert anna.post("/billing/checkout").status_code == 503


# ---------------------------------------------------------------------------
# Fake provider — the local end-to-end path
# ---------------------------------------------------------------------------


def test_fake_checkout_activates_the_subscription(client, session, settings_override):
    settings_override(billing_provider="fake")
    anna = make_player_client(session, client, "Anna", "anna@example.com")

    checkout = anna.post("/billing/checkout")
    assert checkout.status_code == 200
    assert checkout.json()["activated"] is True

    status = anna.get("/billing/status").json()
    assert status["tier"] == "paid"
    assert status["active"] is True
    assert status["valid_until"] is not None


def test_second_checkout_while_active_is_rejected(client, session, settings_override):
    settings_override(billing_provider="fake")
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    anna.post("/billing/checkout")

    assert anna.post("/billing/checkout").status_code == 409


def test_cancel_keeps_access_until_the_period_ends(client, session, settings_override):
    settings_override(billing_provider="fake")
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    anna.post("/billing/checkout")

    cancelled = anna.post("/billing/cancel")
    assert cancelled.status_code == 200
    body = cancelled.json()
    assert body["cancel_at_period_end"] is True
    # Cancelling is not a refund — the paid period still runs.
    assert body["active"] is True
    assert body["tier"] == "paid"


def test_resubscribing_after_cancelling_resumes_instead_of_buying_a_second(
    client, session, settings_override
):
    """The subscription is still live at the provider — checking out again would
    sell a second one and charge for both."""
    settings_override(billing_provider="fake")
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    anna.post("/billing/checkout")
    first_valid_until = anna.get("/billing/status").json()["valid_until"]
    anna.post("/billing/cancel")

    resumed = anna.post("/billing/checkout")
    assert resumed.status_code == 200
    assert resumed.json() == {"checkout_url": None, "activated": True}

    status = anna.get("/billing/status").json()
    assert status["cancel_at_period_end"] is False
    assert status["active"] is True
    # Same period — resuming must not extend or restart the paid term.
    assert status["valid_until"] == first_valid_until


def test_cancel_without_a_subscription_is_rejected(client, session, settings_override):
    settings_override(billing_provider="fake")
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    assert anna.post("/billing/cancel").status_code == 409


def test_paying_removes_the_questionnaire_obligation(client, session, settings_override):
    """The paid tier's actual product: no research questionnaires."""
    settings_override(billing_provider="fake")
    anna = make_player_client(session, client, "Anna", "anna@example.com")
    session.add(ResearchConsent(player_id=anna.id))
    make_finished_duels(session, anna.id, GAMES_REQUIRED_BEFORE_QUESTIONNAIRE)
    session.commit()

    assert get_due_questionnaire(session, anna.id) is not None

    anna.post("/billing/checkout")
    session.expire_all()
    assert get_due_questionnaire(session, anna.id) is None


# ---------------------------------------------------------------------------
# Entitlement expiry
# ---------------------------------------------------------------------------


def test_expired_subscription_is_not_active(session):
    player = make_player(session, "Anna", "anna@example.com")
    player.subscription_tier = SubscriptionTier.PAID
    player.subscription_valid_until = utcnow() - timedelta(minutes=1)
    assert is_subscription_active(player) is False


def test_paid_tier_without_a_valid_until_is_not_active(session):
    """A paid tier with no paid-through date must never count as entitlement."""
    player = make_player(session, "Anna", "anna@example.com")
    player.subscription_tier = SubscriptionTier.PAID
    player.subscription_valid_until = None
    assert is_subscription_active(player) is False


def test_downgrade_job_moves_lapsed_players_back_to_research(session):
    lapsed = make_player(session, "Lapsed", "lapsed@example.com")
    lapsed.subscription_tier = SubscriptionTier.PAID
    lapsed.subscription_valid_until = utcnow() - timedelta(days=1)

    current = make_player(session, "Current", "current@example.com")
    current.subscription_tier = SubscriptionTier.PAID
    current.subscription_valid_until = utcnow() + timedelta(days=10)

    session.add(lapsed)
    session.add(current)
    session.commit()

    assert downgrade_expired_subscriptions(session) == 1

    session.expire_all()
    assert session.get(Player, lapsed.id).subscription_tier == SubscriptionTier.RESEARCH
    assert session.get(Player, current.id).subscription_tier == SubscriptionTier.PAID


def test_lapsed_player_owes_questionnaires_again(session):
    player = make_player(session, "Anna", "anna@example.com")
    player.subscription_tier = SubscriptionTier.PAID
    player.subscription_valid_until = utcnow() - timedelta(days=1)
    session.add(player)
    session.add(ResearchConsent(player_id=player.id))
    make_finished_duels(session, player.id, GAMES_REQUIRED_BEFORE_QUESTIONNAIRE)
    session.commit()

    downgrade_expired_subscriptions(session)
    session.expire_all()
    assert get_due_questionnaire(session, player.id) is not None


# ---------------------------------------------------------------------------
# Stripe webhook handling
# ---------------------------------------------------------------------------


def _player_on_stripe(session):
    player = make_player(session, "Anna", "anna@example.com")
    player.billing_customer_id = "cus_123"
    session.add(player)
    session.commit()
    return player


def test_webhook_checkout_completed_activates(session):
    player = _player_on_stripe(session)
    outcome = handle_stripe_event(
        session,
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_1",
                    "customer": "cus_123",
                    "client_reference_id": str(player.id),
                    "subscription": "sub_123",
                }
            },
        },
    )
    assert outcome == "activated"
    session.expire_all()
    updated = session.get(Player, player.id)
    assert updated.subscription_tier == SubscriptionTier.PAID
    assert updated.billing_subscription_id == "sub_123"
    assert is_subscription_active(updated)


def test_webhook_reads_period_end_from_subscription_items(session):
    """Newer Stripe API versions moved current_period_end onto the items."""
    player = _player_on_stripe(session)
    period_end = int((utcnow() + timedelta(days=30)).timestamp())

    outcome = handle_stripe_event(
        session,
        {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_123",
                    "customer": "cus_123",
                    "status": "active",
                    "items": {"data": [{"current_period_end": period_end}]},
                }
            },
        },
    )
    assert outcome == "updated"
    session.expire_all()
    assert is_subscription_active(session.get(Player, player.id))


def test_webhook_subscription_deleted_downgrades(session):
    player = _player_on_stripe(session)
    player.subscription_tier = SubscriptionTier.PAID
    player.subscription_valid_until = utcnow() + timedelta(days=10)
    session.add(player)
    session.commit()

    outcome = handle_stripe_event(
        session,
        {
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": "sub_123", "customer": "cus_123"}},
        },
    )
    assert outcome == "downgraded"
    session.expire_all()
    assert session.get(Player, player.id).subscription_tier == SubscriptionTier.RESEARCH


def test_webhook_for_unknown_customer_is_ignored(session):
    outcome = handle_stripe_event(
        session,
        {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_1", "customer": "cus_unknown"}},
        },
    )
    assert outcome == "unknown_player"


def test_unrelated_webhook_events_are_ignored(session):
    assert handle_stripe_event(session, {"type": "invoice.created", "data": {"object": {}}}) == (
        "ignored"
    )


def test_webhook_endpoint_requires_configuration(client, settings_override):
    settings_override(stripe_webhook_secret=None)
    assert client.post("/billing/webhook/stripe", json={"type": "x"}).status_code == 503


def test_webhook_endpoint_rejects_a_bad_signature(client, settings_override):
    settings_override(stripe_webhook_secret="whsec_test")
    resp = client.post(
        "/billing/webhook/stripe",
        json={"type": "checkout.session.completed"},
        headers={"stripe-signature": "t=1,v1=forged"},
    )
    assert resp.status_code == 400
