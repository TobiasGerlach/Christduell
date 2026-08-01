import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import CurrentPlayer
from app.core.config import get_settings
from app.db.session import SessionDep
from app.models.domain import SubscriptionTier
from app.services.billing import BillingError, get_provider, handle_stripe_event
from app.services.subscriptions import is_subscription_active

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


class SubscriptionStatus(BaseModel):
    provider: str
    price_eur: str
    tier: SubscriptionTier
    active: bool
    valid_until: datetime | None
    cancel_at_period_end: bool


class CheckoutResponse(BaseModel):
    # None when the provider activated the subscription without a redirect.
    checkout_url: str | None
    activated: bool


@router.get("/status", response_model=SubscriptionStatus)
def get_subscription_status(player: CurrentPlayer) -> SubscriptionStatus:
    settings = get_settings()
    return SubscriptionStatus(
        provider=settings.billing_provider,
        price_eur=settings.subscription_price_eur,
        tier=player.subscription_tier,
        active=is_subscription_active(player),
        valid_until=player.subscription_valid_until,
        cancel_at_period_end=player.subscription_cancel_at_period_end,
    )


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(player: CurrentPlayer, session: SessionDep) -> CheckoutResponse:
    if is_subscription_active(player) and not player.subscription_cancel_at_period_end:
        raise HTTPException(status_code=409, detail="Du hast bereits ein aktives Abo")

    provider = get_provider()

    # Changed your mind after cancelling: the subscription is still live at the
    # provider, so resume it. Starting a checkout here would sell a *second*
    # subscription and charge for both.
    if is_subscription_active(player) and player.subscription_cancel_at_period_end:
        try:
            provider.resume(session, player)
        except BillingError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return CheckoutResponse(checkout_url=None, activated=True)

    try:
        result = provider.create_checkout(session, player)
    except BillingError as exc:
        # 503: the server, not the request, is the problem.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return CheckoutResponse(checkout_url=result.url, activated=result.activated)


@router.post("/cancel", response_model=SubscriptionStatus)
def cancel_subscription(player: CurrentPlayer, session: SessionDep) -> SubscriptionStatus:
    if player.subscription_tier != SubscriptionTier.PAID:
        raise HTTPException(status_code=409, detail="Kein aktives Abo vorhanden")

    provider = get_provider()
    try:
        provider.cancel(session, player)
    except BillingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    session.refresh(player)
    return get_subscription_status(player)


@router.post("/webhook/stripe", status_code=200)
async def stripe_webhook(request: Request, session: SessionDep) -> dict:
    """Receives Stripe subscription lifecycle events.

    The signature check is mandatory: without it anyone who knows the URL could
    grant themselves a subscription by posting a forged event.
    """
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook is not configured")

    import stripe

    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.stripe_webhook_secret
        )
    except Exception as exc:  # noqa: BLE001 — bad signature or malformed body
        logger.warning("rejected stripe webhook: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid webhook signature") from exc

    outcome = handle_stripe_event(session, dict(event))
    logger.info("stripe webhook %s → %s", event.get("type"), outcome)
    return {"status": outcome}
