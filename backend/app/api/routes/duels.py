from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.db.session import SessionDep
from app.models.domain import Duel, Player

router = APIRouter(prefix="/duels", tags=["duels"])


class DuelCreateRequest(BaseModel):
    challenger_id: int
    opponent_id: int


@router.post("", response_model=Duel, status_code=201)
def create_duel(payload: DuelCreateRequest, session: SessionDep) -> Duel:
    for player_id in (payload.challenger_id, payload.opponent_id):
        if session.get(Player, player_id) is None:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    duel = Duel(challenger_id=payload.challenger_id, opponent_id=payload.opponent_id)
    session.add(duel)
    session.commit()
    session.refresh(duel)
    return duel


@router.get("/{duel_id}", response_model=Duel)
def get_duel(duel_id: int, session: SessionDep) -> Duel:
    duel = session.get(Duel, duel_id)
    if duel is None:
        raise HTTPException(status_code=404, detail="Duel not found")
    return duel


@router.get("", response_model=list[Duel])
def list_duels_for_player(player_id: int, session: SessionDep) -> list[Duel]:
    statement = select(Duel).where(
        (Duel.challenger_id == player_id) | (Duel.opponent_id == player_id)
    )
    return list(session.exec(statement))
