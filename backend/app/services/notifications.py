import logging

from app.models.domain import Duel, DuelRound

logger = logging.getLogger(__name__)


def notify_opponent_answered(duel: Duel, duel_round: DuelRound, answering_player_id: int) -> None:
    """Trigger hook for "your opponent just answered" push alerts.

    Stub for the later phase that wires up Azure Notification Hub sending —
    for now it only logs, so the call site and trigger condition (fires once
    per scored answer) are already correct and won't need touching later.
    """
    logger.info(
        "duel %s round %s: player %s answered — opponent should be notified",
        duel.id,
        duel_round.sequence,
        answering_player_id,
    )
