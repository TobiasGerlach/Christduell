"""Domain events that deserve a push notification.

Each function maps a game event to the message(s) it produces and hands them to
`app.services.push`. Keeping the wording here (rather than at the call sites)
means the German copy lives in one place.
"""

import logging

from sqlmodel import Session

from app.models.domain import Duel, Player
from app.services import push
from app.services.duel_state import compute_duel_scores

logger = logging.getLogger(__name__)


def _player(session: Session, player_id: int) -> Player | None:
    player = session.get(Player, player_id)
    if player is None or player.deleted_at is not None:
        return None
    return player


def notify_challenged(opponent: Player, challenger: Player, duel: Duel) -> None:
    if opponent.deleted_at is not None:
        return
    push.send(
        [
            push.PushMessage(
                to=opponent.push_token,
                title="Neue Herausforderung",
                body=f"{challenger.display_name} fordert dich zum Duell heraus!",
                data={"type": "duel_challenge", "duelId": duel.id},
            )
        ]
    )


def notify_your_turn(session: Session, duel: Duel, player_id: int, opponent: Player) -> None:
    player = _player(session, player_id)
    if player is None:
        return
    push.send(
        [
            push.PushMessage(
                to=player.push_token,
                title="Du bist dran",
                body=f"{opponent.display_name} hat gespielt — jetzt bist du am Zug.",
                data={"type": "duel_turn", "duelId": duel.id},
            )
        ]
    )


def notify_duel_finished(session: Session, duel: Duel) -> None:
    challenger_score, opponent_score = compute_duel_scores(session, duel)
    messages: list[push.PushMessage] = []

    for player_id, own_score, other_score in (
        (duel.challenger_id, challenger_score, opponent_score),
        (duel.opponent_id, opponent_score, challenger_score),
    ):
        player = _player(session, player_id)
        if player is None:
            continue
        if own_score > other_score:
            body = f"Du hast gewonnen — {own_score}:{other_score}!"
        elif own_score < other_score:
            body = f"Du hast verloren — {own_score}:{other_score}."
        else:
            body = f"Unentschieden — {own_score}:{other_score}."
        messages.append(
            push.PushMessage(
                to=player.push_token,
                title="Duell beendet",
                body=body,
                data={"type": "duel_finished", "duelId": duel.id},
            )
        )

    push.send(messages)
