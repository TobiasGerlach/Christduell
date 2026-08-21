from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.api.deps import CurrentPlayer
from app.core.config import get_settings
from app.db.session import SessionDep
from app.models.domain import Player, WebPushSubscription

router = APIRouter(prefix="/notifications", tags=["notifications"])


class RegisterPushTokenRequest(BaseModel):
    push_token: str


@router.post("/register-token", status_code=204)
def register_push_token(
    payload: RegisterPushTokenRequest, player: CurrentPlayer, session: SessionDep
) -> None:
    """Store a push token so the backend can send this player duel alerts."""
    # A token identifies a device, not a person. If someone else was signed in
    # on this device before, detach it from them — otherwise the previous
    # account keeps receiving notifications on a phone that is no longer theirs.
    previous = session.exec(
        select(Player).where(
            Player.push_token == payload.push_token,
            Player.id != player.id,
        )
    )
    for other in previous:
        other.push_token = None
        session.add(other)

    player.push_token = payload.push_token
    session.add(player)
    session.commit()


@router.delete("/register-token", status_code=204)
def clear_push_token(player: CurrentPlayer, session: SessionDep) -> None:
    """Stop sending pushes to this device (used on logout)."""
    player.push_token = None
    session.add(player)
    session.commit()


class WebPushKeys(BaseModel):
    p256dh: str
    auth: str


class WebPushSubscribeRequest(BaseModel):
    endpoint: str
    keys: WebPushKeys


class WebPushPublicKeyResponse(BaseModel):
    public_key: str


@router.get("/web-push/public-key", response_model=WebPushPublicKeyResponse)
def web_push_public_key() -> WebPushPublicKeyResponse:
    """The VAPID public key the browser needs to subscribe. 404 = not configured."""
    settings = get_settings()
    if not settings.web_push_enabled:
        raise HTTPException(status_code=404, detail="Web Push ist nicht konfiguriert")
    return WebPushPublicKeyResponse(public_key=settings.vapid_public_key)


@router.post("/web-push/subscriptions", status_code=204)
def subscribe_web_push(
    payload: WebPushSubscribeRequest, player: CurrentPlayer, session: SessionDep
) -> None:
    """Store this browser's push subscription for the signed-in player.

    An endpoint identifies a browser profile, not a person — if it already
    exists it moves to the current player (same reasoning as register-token).
    """
    existing = session.exec(
        select(WebPushSubscription).where(WebPushSubscription.endpoint == payload.endpoint)
    ).first()
    if existing is not None:
        existing.player_id = player.id
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
        session.add(existing)
    else:
        session.add(
            WebPushSubscription(
                player_id=player.id,
                endpoint=payload.endpoint,
                p256dh=payload.keys.p256dh,
                auth=payload.keys.auth,
            )
        )
    session.commit()


@router.delete("/web-push/subscriptions", status_code=204)
def unsubscribe_web_push(endpoint: str, player: CurrentPlayer, session: SessionDep) -> None:
    """Drop this browser's subscription (used on logout / opt-out)."""
    subscription = session.exec(
        select(WebPushSubscription).where(WebPushSubscription.endpoint == endpoint)
    ).first()
    if subscription is not None and subscription.player_id == player.id:
        session.delete(subscription)
        session.commit()
