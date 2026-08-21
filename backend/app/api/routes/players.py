from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import col, or_, select

from app.api.deps import CurrentPlayer
from app.db.session import SessionDep
from app.models.domain import Player
from app.services.rating import emoji_for_rank, rank_for_rating

router = APIRouter(prefix="/players", tags=["players"])

SEARCH_RESULT_LIMIT = 10
LIKE_ESCAPE = "\\"


def escape_like(term: str) -> str:
    """Neutralises LIKE wildcards in user input.

    Without this, searching for `%%%` matches every display name and turns this
    endpoint into a dump of the player table.
    """
    for character in (LIKE_ESCAPE, "%", "_"):
        term = term.replace(character, LIKE_ESCAPE + character)
    return term


class PlayerProfile(BaseModel):
    id: int
    display_name: str
    rating: float
    rank: str
    rank_emoji: str


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
            or_(
                Player.email == term,
                col(Player.display_name).ilike(f"{escape_like(term)}%", escape=LIKE_ESCAPE),
            ),
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
        rank_emoji=emoji_for_rank(rank_for_rating(player.rating)),
    )
