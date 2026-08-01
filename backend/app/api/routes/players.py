from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import col, or_, select

from app.api.deps import CurrentPlayer
from app.db.session import SessionDep
from app.models.domain import Player
from app.services.rating import rank_for_rating

router = APIRouter(prefix="/players", tags=["players"])

SEARCH_RESULT_LIMIT = 10


class PlayerProfile(BaseModel):
    id: int
    display_name: str
    rating: float
    rank: str


@router.get("/search", response_model=list[PlayerProfile])
def search_players(
    player: CurrentPlayer,
    session: SessionDep,
    q: str = Query(min_length=3, description="Email address or start of a display name"),
) -> list[PlayerProfile]:
    """Finds opponents to challenge.

    Email matches must be exact — a prefix search over addresses would turn this
    endpoint into a way to harvest other people's email addresses. Display names
    are matched by prefix, and no endpoint ever returns another player's email.
    """
    term = q.strip().lower()
    statement = (
        select(Player)
        .where(
            Player.id != player.id,
            Player.deleted_at.is_(None),
            or_(Player.email == term, col(Player.display_name).ilike(f"{term}%")),
        )
        .order_by(col(Player.rating).desc())
        .limit(SEARCH_RESULT_LIMIT)
    )
    return [_to_profile(found) for found in session.exec(statement)]


@router.get("/{player_id}", response_model=PlayerProfile)
def get_player_profile(
    player_id: int, player: CurrentPlayer, session: SessionDep
) -> PlayerProfile:
    found = session.get(Player, player_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return _to_profile(found)


def _to_profile(player: Player) -> PlayerProfile:
    return PlayerProfile(
        id=player.id,
        display_name=player.display_name,
        rating=player.rating,
        rank=rank_for_rating(player.rating),
    )
