import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.deps import CurrentPlayer
from app.core.security import create_access_token, hash_password, verify_password
from app.core.time import utcnow
from app.db.session import SessionDep
from app.models.domain import Player, ResearchConsent, SubscriptionTier
from app.services.rating import rank_for_rating
from app.services.subscriptions import is_subscription_active

router = APIRouter(prefix="/auth", tags=["auth"])

MIN_PASSWORD_LENGTH = 8


class RegisterRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=40)
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AccountResponse(BaseModel):
    id: int
    display_name: str
    email: str
    rating: float
    rank: str
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
        subscription_tier=player.subscription_tier,
        subscription_active=is_subscription_active(player),
        subscription_valid_until=player.subscription_valid_until,
        subscription_cancel_at_period_end=player.subscription_cancel_at_period_end,
    )


def find_by_email(session: Session, email: str) -> Player | None:
    return session.exec(select(Player).where(Player.email == email.strip().lower())).first()


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, session: SessionDep) -> TokenResponse:
    email = payload.email.strip().lower()
    if find_by_email(session, email) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    player = Player(
        display_name=payload.display_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
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
    player = find_by_email(session, payload.email)
    # Same error for "no such account" and "wrong password" so the endpoint
    # can't be used to enumerate registered email addresses.
    invalid = HTTPException(status_code=401, detail="Invalid email or password")
    if player is None or player.password_hash is None or player.deleted_at is not None:
        raise invalid
    if not verify_password(payload.password, player.password_hash):
        raise invalid

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
