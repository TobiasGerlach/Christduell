"""Abandoned duels must close themselves.

Without expiry, a player who quits mid-duel leaves the opponent on "opponent's
turn" forever and blocks that pairing in random matchmaking. The maintenance
job closes anything untouched for the configured number of days.
"""

from datetime import timedelta

from sqlmodel import select

from app.core.time import utcnow
from app.models.domain import Category, Duel, DuelAnswer, DuelRound, DuelStatus
from app.services.duel_expiry import expire_inactive_duels, last_activity
from tests.factories import make_questions_for_category

LONG_AGO = utcnow() - timedelta(days=30)


def _backdate_everything(session, duel_id: int) -> None:
    duel = session.get(Duel, duel_id)
    duel.created_at = LONG_AGO
    session.add(duel)
    for duel_round in session.exec(select(DuelRound).where(DuelRound.duel_id == duel_id)):
        duel_round.created_at = LONG_AGO
        session.add(duel_round)
        for answer in session.exec(
            select(DuelAnswer).where(DuelAnswer.round_id == duel_round.id)
        ):
            answer.shown_at = LONG_AGO
            if answer.answered_at is not None:
                answer.answered_at = LONG_AGO
            session.add(answer)
    session.commit()


def _start_round(session, duel, category=Category.HISTORY):
    make_questions_for_category(session, category, 3)
    round_id = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds", json={"category": category.value}
    ).json()["round_id"]
    duel.challenger.get(f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1")
    duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1/answer",
        json={"selected_choice_index": 0},
    )
    return round_id


def test_a_stale_pending_challenge_quietly_disappears(session, duel):
    _backdate_everything(session, duel.duel_id)

    assert expire_inactive_duels(session) == 1

    session.expire_all()
    assert session.get(Duel, duel.duel_id).status == DuelStatus.DECLINED
    # Declined duels are filtered out of both players' lists.
    assert duel.challenger.get("/duels").json() == []


def test_an_abandoned_active_duel_ends_at_the_current_score(
    session, duel, captured_pushes
):
    _start_round(session, duel)
    _backdate_everything(session, duel.duel_id)

    assert expire_inactive_duels(session) == 1

    session.expire_all()
    closed = session.get(Duel, duel.duel_id)
    assert closed.status == DuelStatus.FINISHED
    assert closed.finished_at is not None
    # Both players hear about it.
    finished_pushes = [m for m in captured_pushes if m.data.get("type") == "duel_finished"]
    assert len(finished_pushes) == 2


def test_an_expired_duel_cannot_be_played_any_further(session, duel):
    round_id = _start_round(session, duel)
    _backdate_everything(session, duel.duel_id)
    expire_inactive_duels(session)

    # The state machine reports it closed, so every move is out of turn now.
    state = duel.challenger.get(f"/duels/{duel.duel_id}/state").json()
    assert state["action"] == "finished"

    answer = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/2/answer",
        json={"selected_choice_index": 0},
    )
    assert answer.status_code == 409


def test_recent_activity_keeps_a_duel_alive(session, duel):
    """created_at may be ancient — what counts is the last move."""
    _start_round(session, duel)
    _backdate_everything(session, duel.duel_id)

    # One fresh answer view resets the clock.
    duel.challenger.get(
        f"/duels/{duel.duel_id}/rounds/"
        f"{session.exec(select(DuelRound.id)).first()}/questions/2"
    )

    assert expire_inactive_duels(session) == 0
    session.expire_all()
    assert session.get(Duel, duel.duel_id).status == DuelStatus.ACTIVE


def test_last_activity_prefers_the_newest_timestamp(session, duel):
    _start_round(session, duel)
    duel_row = session.get(Duel, duel.duel_id)
    assert last_activity(session, duel_row) > duel_row.created_at - timedelta(seconds=1)


def test_expired_pairs_can_be_matched_randomly_again(client, session, duel):
    """The whole point: an abandoned duel must not poison matchmaking forever."""
    _backdate_everything(session, duel.duel_id)
    expire_inactive_duels(session)

    resp = duel.challenger.post("/duels/random")
    assert resp.status_code == 201
    assert resp.json()["opponent_id"] == duel.opponent.id
