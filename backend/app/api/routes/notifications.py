from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentPlayer
from app.db.session import SessionDep

router = APIRouter(prefix="/notifications", tags=["notifications"])


class RegisterPushTokenRequest(BaseModel):
    push_token: str


@router.post("/register-token", status_code=204)
def register_push_token(
    payload: RegisterPushTokenRequest, player: CurrentPlayer, session: SessionDep
) -> None:
    """Store a push token so the backend can send this player duel alerts."""
    player.push_token = payload.push_token
    session.add(player)
    session.commit()


@router.delete("/register-token", status_code=204)
def clear_push_token(player: CurrentPlayer, session: SessionDep) -> None:
    """Stop sending pushes to this device (used on logout)."""
    player.push_token = None
    session.add(player)
    session.commit()
