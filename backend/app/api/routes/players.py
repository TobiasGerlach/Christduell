from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.session import SessionDep
from app.models.domain import Player
from app.services.rating import rank_for_rating

router = APIRouter(prefix="/players", tags=["players"])


class PlayerProfile(BaseModel):
    id: int
    display_name: str
    rating: float
    rank: str


@router.get("/{player_id}", response_model=PlayerProfile)
def get_player_profile(player_id: int, session: SessionDep) -> PlayerProfile:
    player = session.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return PlayerProfile(
        id=player.id,
        display_name=player.display_name,
        rating=player.rating,
        rank=rank_for_rating(player.rating),
    )
