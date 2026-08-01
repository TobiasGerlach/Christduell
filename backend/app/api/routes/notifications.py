from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import select

from app.api.deps import CurrentPlayer
from app.db.session import SessionDep
from app.models.domain import Player

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
