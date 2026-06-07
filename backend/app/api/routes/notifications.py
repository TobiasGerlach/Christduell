from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.session import SessionDep
from app.models.domain import Player

router = APIRouter(prefix="/notifications", tags=["notifications"])


class RegisterPushTokenRequest(BaseModel):
    player_id: int
    push_token: str


@router.post("/register-token", status_code=204)
def register_push_token(payload: RegisterPushTokenRequest, session: SessionDep) -> None:
    """Store a push token so the backend can later send the player duel alerts."""
    player = session.get(Player, payload.player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    player.push_token = payload.push_token
    session.add(player)
    session.commit()
