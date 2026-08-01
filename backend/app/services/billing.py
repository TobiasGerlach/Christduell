"""Subscription billing.

Three providers, chosen with the `BILLING_PROVIDER` setting:

- ``none``   — subscriptions are switched off; checkout returns 503. This is the
  safe default so a half-configured deployment can never take money.
- ``fake``   — local development and tests: "checkout" grants 30 days instantly,
  so the paid tier can be exercised end to end without Stripe credentials.
- ``stripe`` — real Stripe Checkout subscriptions, confirmed by webhook.

Stripe covers the **web** build only. Apple and Google require in-app purchase
for digital subscriptions inside their apps, which is a different integration
(see todos.md) — this module is deliberately provider-shaped so that lands as a
fourth implementation rather than a rewrite.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.core.time import utcnow
from app.models.domain import Player
from app.services.subscriptions import activate_paid, downgrade_to_research, mark_cancelled

logger = logging.getLogger(__name__)

FAKE_SUBSCRIPTION_DAYS = 30


class BillingError(Exception):
    """Raised for configuration or provider failures; routes map this to 503/502."""


@dataclass
class CheckoutResult:
    # Where to send the browser. None means the subscription was activated
    # without a redirect (fake provider).
    url: str | None
    activated: bool


class BillingProvider:
    name = "none"

    def create_checkout(self, session: Session, player: Player) -> CheckoutResult:
        raise BillingError("Subscriptions are not enabled on this server")

    def cancel(self, session: Session, player: Player) -> None:
        raise BillingError("Subscriptions are not enabled on this server")


class FakeBillingProvider(BillingProvider):
    """Grants a subscription immediately. Never enable this in production."""

    name = "fake"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_checkout(self, session: Session, player: Player) -> CheckoutResult:
        activate_paid(
            session,
            player,
            valid_until=utcnow() + timedelta(days=FAKE_SUBSCRIPTION_DAYS),
            customer_id=f"fake_cus_{player.id}",
            subscription_id=f"fake_sub_{player.id}",
        )
        return CheckoutResult(url=self._settings.billing_success_url, activated=True)

    def cancel(self, session: Session, player: Player) -> None:
        mark_cancelled(session, player)


class StripeBillingProvider(BillingProvider):
    name = "stripe"

    def __init__(self, settings: Settings) -> None:
        if not settings.stripe_secret_key or not settings.stripe_price_id:
            raise BillingError("STRIPE_SECRET_KEY and STRIPE_PRICE_ID must be set")
        self._settings = settings

    @property
    def _stripe(self):
        import stripe

        stripe.api_key = self._settings.stripe_secret_key
        return stripe

    def _ensure_customer(self, session: Session, player: Player) -> str:
        if player.billing_customer_id:
            return player.billing_customer_id
        customer = self._stripe.Customer.create(
            email=player.email,
            name=player.display_name,
            metadata={"player_id": str(player.id)},
        )
        player.billing_customer_id = customer.id
        session.add(player)
        session.commit()
        session.refresh(player)
        return customer.id

    def create_checkout(self, session: Session, player: Player) -> CheckoutResult:
        try:
            customer_id = self._ensure_customer(session, player)
            checkout = self._stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                client_reference_id=str(player.id),
                line_items=[{"price": self._settings.stripe_price_id, "quantity": 1}],
                success_url=self._settings.billing_success_url,
                cancel_url=self._settings.billing_cancel_url,
                # Stripe collects the VAT-relevant address and applies the
                # automatic tax rules configured in the dashboard.
                automatic_tax={"enabled": True},
                customer_update={"address": "auto"},
            )
        except Exception as exc:  # noqa: BLE001 — surfaced as a 502 by the route
            raise BillingError(f"Stripe checkout failed: {exc}") from exc

        return CheckoutResult(url=checkout.url, activated=False)

    def cancel(self, session: Session, player: Player) -> None:
        if not player.billing_subscription_id:
            raise BillingError("No active subscription to cancel")
        try:
            self._stripe.Subscription.modify(
                player.billing_subscription_id, cancel_at_period_end=True
            )
        except Exception as exc:  # noqa: BLE001
            raise BillingError(f"Stripe cancellation failed: {exc}") from exc
        mark_cancelled(session, player)


def get_provider(settings: Settings | None = None) -> BillingProvider:
    settings = settings or get_settings()
    if settings.billing_provider == "fake":
        return FakeBillingProvider(settings)
    if settings.billing_provider == "stripe":
        return StripeBillingProvider(settings)
    return BillingProvider()


# ---------------------------------------------------------------------------
# Stripe webhook handling
# ---------------------------------------------------------------------------


def _period_end(subscription: dict) -> datetime | None:
    """Reads the paid-through timestamp out of a Stripe subscription object.

    Newer Stripe API versions moved `current_period_end` from the subscription
    onto its items, so both shapes are accepted.
    """
    timestamp = subscription.get("current_period_end")
    if timestamp is None:
        items = (subscription.get("items") or {}).get("data") or []
        if items:
            timestamp = items[0].get("current_period_end")
    if timestamp is None:
        return None
    # Stored naive like every other timestamp column.
    return datetime.fromtimestamp(int(timestamp), UTC).replace(tzinfo=None)


def _find_player(
    session: Session, *, customer_id: str | None, player_id: str | None
) -> Player | None:
    if player_id:
        try:
            player = session.get(Player, int(player_id))
        except (TypeError, ValueError):
            player = None
        if player is not None:
            return player
    if customer_id:
        return session.exec(
            select(Player).where(Player.billing_customer_id == customer_id)
        ).first()
    return None


def handle_stripe_event(session: Session, event: dict) -> str:
    """Applies a Stripe webhook event. Returns a short outcome for logging/tests.

    Only subscription lifecycle events matter; anything else is acknowledged and
    ignored so Stripe doesn't retry it forever.
    """
    event_type = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}

    if event_type == "checkout.session.completed":
        player = _find_player(
            session,
            customer_id=obj.get("customer"),
            player_id=obj.get("client_reference_id"),
        )
        if player is None:
            logger.warning("stripe checkout completed for unknown player: %s", obj.get("id"))
            return "unknown_player"
        subscription_id = obj.get("subscription")
        valid_until = utcnow() + timedelta(days=FAKE_SUBSCRIPTION_DAYS)
        activate_paid(
            session,
            player,
            valid_until=valid_until,
            customer_id=obj.get("customer"),
            subscription_id=subscription_id,
        )
        # The exact period end arrives with customer.subscription.updated; the
        # 30-day placeholder above only bridges the gap between the two events.
        return "activated"

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        player = _find_player(
            session,
            customer_id=obj.get("customer"),
            player_id=(obj.get("metadata") or {}).get("player_id"),
        )
        if player is None:
            return "unknown_player"

        status = obj.get("status")
        period_end = _period_end(obj)
        if status in ("active", "trialing") and period_end is not None:
            activate_paid(
                session,
                player,
                valid_until=period_end,
                customer_id=obj.get("customer"),
                subscription_id=obj.get("id"),
            )
            if obj.get("cancel_at_period_end"):
                mark_cancelled(session, player)
            return "updated"

        if status in ("canceled", "unpaid", "incomplete_expired"):
            downgrade_to_research(session, player)
            return "downgraded"
        return "ignored_status"

    if event_type == "customer.subscription.deleted":
        player = _find_player(
            session,
            customer_id=obj.get("customer"),
            player_id=(obj.get("metadata") or {}).get("player_id"),
        )
        if player is None:
            return "unknown_player"
        downgrade_to_research(session, player)
        return "downgraded"

    return "ignored"
