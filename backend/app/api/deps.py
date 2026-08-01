from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.db.session import SessionDep
from app.models.domain import Player

# auto_error=False so a missing header produces our own 401 with a consistent
# body rather than FastAPI's 403.
bearer_scheme = HTTPBearer(auto_error=False, description="Bearer token from /auth/login")

_UNAUTHENTICATED = HTTPException(
    status_code=401,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_player(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> Player:
    """Resolves the authenticated player from the bearer token.

    Every player-scoped endpoint depends on this instead of accepting a
    `player_id` parameter — the client cannot choose whose data it acts on.
    """
    if credentials is None:
        raise _UNAUTHENTICATED

    player_id = decode_access_token(credentials.credentials)
    if player_id is None:
        raise _UNAUTHENTICATED

    player = session.get(Player, player_id)
    if player is None or player.deleted_at is not None:
        raise _UNAUTHENTICATED

    return player


CurrentPlayer = Annotated[Player, Depends(get_current_player)]
