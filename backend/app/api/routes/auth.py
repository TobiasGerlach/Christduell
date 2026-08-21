import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.deps import CurrentPlayer
from app.core.config import get_settings
from app.core.ratelimit import limiter
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    decode_password_reset_token,
    hash_password,
    verify_password,
)
from app.core.time import utcnow
from app.db.session import SessionDep
from app.models.domain import Player, ResearchConsent, SubscriptionTier
from app.services import email as email_service
from app.services.rating import (
    division_for_rating,
    emoji_for_rank,
    ladder_step_for_rating,
    rank_for_rating,
)
from app.services.subscriptions import is_subscription_active

router = APIRouter(prefix="/auth", tags=["auth"])

MIN_PASSWORD_LENGTH = 8

# Verified against when no account matches, so "unknown address" and "wrong
# password" take the same time — otherwise response timing reveals whether an
# email is registered.
_TIMING_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")

_TOO_MANY_ATTEMPTS = HTTPException(
    status_code=429, detail="Zu viele Versuche. Bitte warte ein paar Minuten."
)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class RegisterRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=40)
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
    # GDPR Art. 8: the consent age in Germany is 16. Younger players need their
    # parents' consent, which an organiser (e.g. a youth group) can collect on
    # paper — hence the "or my guardians agree" wording in the app.
    min_age_confirmed: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AccountResponse(BaseModel):
    id: int
    display_name: str
    email: str
    rating: float
    rank: str
    rank_emoji: str
    rank_division: int
    ladder_step: int
    subscription_tier: SubscriptionTier
    subscription_active: bool
    subscription_valid_until: datetime | None
    subscription_cancel_at_period_end: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    player: AccountResponse


def to_account(player: Player) -> AccountResponse:
    return AccountResponse(
        id=player.id,
        display_name=player.display_name,
        email=player.email,
        rating=player.rating,
        rank=rank_for_rating(player.rating),
        rank_emoji=emoji_for_rank(rank_for_rating(player.rating)),
        rank_division=division_for_rating(player.rating),
        ladder_step=ladder_step_for_rating(player.rating),
        subscription_tier=player.subscription_tier,
        subscription_active=is_subscription_active(player),
        subscription_valid_until=player.subscription_valid_until,
        subscription_cancel_at_period_end=player.subscription_cancel_at_period_end,
    )


def find_by_email(session: Session, email: str) -> Player | None:
    return session.exec(select(Player).where(Player.email == email.strip().lower())).first()


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, request: Request, session: SessionDep) -> TokenResponse:
    settings = get_settings()
    register_key = f"register:{_client_ip(request)}"
    if limiter.blocked(
        register_key,
        settings.register_rate_limit_attempts,
        settings.register_rate_limit_window_seconds,
    ):
        raise _TOO_MANY_ATTEMPTS
    limiter.record(register_key, settings.register_rate_limit_window_seconds)

    if not payload.min_age_confirmed:
        raise HTTPException(
            status_code=400,
            detail=(
                "Bitte bestätige, dass du mindestens 16 Jahre alt bist "
                "oder deine Erziehungsberechtigten einverstanden sind"
            ),
        )

    email = payload.email.strip().lower()
    if find_by_email(session, email) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    player = Player(
        display_name=payload.display_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        min_age_confirmed_at=utcnow(),
    )
    session.add(player)
    try:
        session.commit()
    except IntegrityError:
        # Two registrations for the same address raced past the check above;
        # the unique index caught it. Same answer as the check would have given.
        session.rollback()
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        ) from None
    session.refresh(player)

    return TokenResponse(access_token=create_access_token(player.id), player=to_account(player))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    settings = get_settings()
    # Limited per account, not per IP: a whole youth group behind one church
    # wifi must not be able to lock each other out, but ten failures against a
    # single mailbox is a guessing loop.
    login_key = f"login:{payload.email.strip().lower()}"
    if limiter.blocked(
        login_key,
        settings.login_rate_limit_attempts,
        settings.login_rate_limit_window_seconds,
    ):
        raise _TOO_MANY_ATTEMPTS

    player = find_by_email(session, payload.email)
    # Same error for "no such account" and "wrong password" so the endpoint
    # can't be used to enumerate registered email addresses.
    invalid = HTTPException(status_code=401, detail="Invalid email or password")
    if player is None or player.password_hash is None or player.deleted_at is not None:
        verify_password(payload.password, _TIMING_DUMMY_HASH)
        limiter.record(login_key, settings.login_rate_limit_window_seconds)
        raise invalid
    if not verify_password(payload.password, player.password_hash):
        limiter.record(login_key, settings.login_rate_limit_window_seconds)
        raise invalid

    limiter.clear(login_key)
    return TokenResponse(access_token=create_access_token(player.id), player=to_account(player))


@router.get("/me", response_model=AccountResponse)
def get_me(player: CurrentPlayer) -> AccountResponse:
    return to_account(player)


class UpdateMeRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=40)


@router.patch("/me", response_model=AccountResponse)
def update_me(payload: UpdateMeRequest, player: CurrentPlayer, session: SessionDep):
    player.display_name = payload.display_name.strip()
    session.add(player)
    session.commit()
    session.refresh(player)
    return to_account(player)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)


@router.post("/change-password", status_code=204)
def change_password(
    payload: ChangePasswordRequest, player: CurrentPlayer, session: SessionDep
) -> None:
    if player.password_hash is None or not verify_password(
        payload.current_password, player.password_hash
    ):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    player.password_hash = hash_password(payload.new_password)
    session.add(player)
    session.commit()


@router.delete("/me", status_code=204)
def delete_account(player: CurrentPlayer, session: SessionDep) -> None:
    """Deletes the account (GDPR erasure; also required by the app stores).

    A soft delete: personal data is overwritten in place and the login is
    disabled, but the row stays so historical duels remain consistent. Any
    research consent is withdrawn at the same time, which severs the link
    between this person and their already-anonymised questionnaire answers.
    """
    consent = session.get(ResearchConsent, player.id)
    if consent is not None and consent.withdrawn_at is None:
        consent.withdrawn_at = utcnow()
        session.add(consent)

    player.display_name = "Gelöschter Spieler"
    # Keep the column unique without retaining the address.
    player.email = f"deleted+{uuid.uuid4().hex}@christduell.invalid"
    player.password_hash = None
    player.push_token = None
    player.deleted_at = utcnow()
    session.add(player)
    session.commit()


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)


@router.post("/forgot-password", status_code=204)
def forgot_password(
    payload: ForgotPasswordRequest, request: Request, session: SessionDep
) -> None:
    """Emails a reset link. Always 204 — the response never reveals whether
    the address has an account (same reasoning as the login error)."""
    settings = get_settings()
    key = f"forgot:{_client_ip(request)}"
    if limiter.blocked(key, settings.register_rate_limit_attempts,
                       settings.register_rate_limit_window_seconds):
        raise _TOO_MANY_ATTEMPTS
    limiter.record(key, settings.register_rate_limit_window_seconds)

    player = find_by_email(session, payload.email)
    if player is None or player.deleted_at is not None:
        return

    token = create_password_reset_token(player.id, player.password_hash)
    base = settings.public_base_url.rstrip("/") or str(request.base_url).rstrip("/")
    link = f"{base}/passwort-zuruecksetzen?token={token}"
    email_service.send(
        to=player.email,
        subject="Christduell — Passwort zurücksetzen",
        body=(
            f"Hallo {player.display_name},\n\n"
            f"jemand (hoffentlich du) möchte dein Christduell-Passwort zurücksetzen.\n"
            f"Der Link ist 60 Minuten gültig:\n\n{link}\n\n"
            f"Wenn du das nicht warst, kannst du diese E-Mail ignorieren — "
            f"dein Passwort bleibt unverändert.\n"
        ),
    )


@router.post("/reset-password", status_code=204)
def reset_password(payload: ResetPasswordRequest, session: SessionDep) -> None:
    """Sets a new password from an emailed token. Tokens are single-use: they
    fingerprint the current hash, so the first successful reset kills them."""

    def lookup(player_id: int) -> str | None:
        player = session.get(Player, player_id)
        if player is None or player.deleted_at is not None:
            return None
        return player.password_hash

    player_id = decode_password_reset_token(payload.token, lookup)
    if player_id is None:
        raise HTTPException(
            status_code=400,
            detail="Der Link ist abgelaufen oder wurde schon benutzt. Fordere einen neuen an.",
        )
    player = session.get(Player, player_id)
    player.password_hash = hash_password(payload.new_password)
    session.add(player)
    session.commit()
