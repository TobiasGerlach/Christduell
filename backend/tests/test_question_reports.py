"""Reporting is the review mechanism for a bank too large to proofread.

The rules that matter: you can only report what you played, one report per
person per question, and enough people disputing a question pulls it out of
circulation on its own.
"""

import pytest
from sqlmodel import select

from app.core.time import utcnow
from app.models.domain import Category, Question, QuestionReport, ReportStatus
from app.services.question_reports import count_retiring_reports, resolve, restore
from app.services.question_selection import select_questions_for_round
from tests.factories import (
    answer_all_questions,
    make_player_client,
    make_question,
    make_questions_for_category,
    play_round,
)


@pytest.fixture(name="played")
def played_fixture(session, duel):
    """A finished round, so both players are allowed to report its questions."""
    play_round(session, duel.duel_id, duel.challenger, duel.opponent, Category.HISTORY)
    question = session.exec(select(Question).where(Question.category == Category.HISTORY)).first()
    return question


def test_reporting_a_played_question_is_recorded(session, duel, played):
    resp = duel.challenger.post(
        f"/questions/{played.id}/report",
        json={"reason": "wrong_answer", "note": "Die Jahreszahl stimmt nicht"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json() == {"status": "received", "question_retired": False}

    report = session.exec(select(QuestionReport)).one()
    assert report.question_id == played.id
    assert report.player_id == duel.challenger.id
    assert report.note == "Die Jahreszahl stimmt nicht"
    assert report.status == ReportStatus.OPEN


def test_cannot_report_a_question_you_never_played(client, session, duel, played):
    outsider = make_player_client(session, client, "Outsider", "outsider@example.com")
    resp = outsider.post(f"/questions/{played.id}/report", json={"reason": "wrong_answer"})
    assert resp.status_code == 403


def test_reporting_requires_authentication(client, played):
    resp = client.post(f"/questions/{played.id}/report", json={"reason": "wrong_answer"})
    assert resp.status_code == 401


def test_unknown_question_is_404(duel):
    resp = duel.challenger.post("/questions/999999/report", json={"reason": "typo"})
    assert resp.status_code == 404


def test_reason_must_be_a_known_value(duel, played):
    resp = duel.challenger.post(f"/questions/{played.id}/report", json={"reason": "weil"})
    assert resp.status_code == 422


def test_one_report_per_player_and_reports_can_be_changed(session, duel, played):
    duel.challenger.post(f"/questions/{played.id}/report", json={"reason": "typo"})
    duel.challenger.post(
        f"/questions/{played.id}/report", json={"reason": "wrong_answer", "note": "doch falsch"}
    )

    reports = list(session.exec(select(QuestionReport)))
    assert len(reports) == 1, "reporting twice must update, not stack up"
    assert reports[0].reason.value == "wrong_answer"
    assert reports[0].note == "doch falsch"


def test_one_annoyed_player_cannot_retire_a_question(session, duel, played, settings_override):
    settings_override(question_report_retire_threshold=3)
    for _ in range(3):
        duel.challenger.post(f"/questions/{played.id}/report", json={"reason": "wrong_answer"})

    session.expire_all()
    assert session.get(Question, played.id).retired_at is None
    assert count_retiring_reports(session, played.id) == 1


def test_enough_distinct_reports_retire_the_question(session, duel, played, settings_override):
    settings_override(question_report_retire_threshold=2)

    first = duel.challenger.post(f"/questions/{played.id}/report", json={"reason": "wrong_answer"})
    assert first.json()["question_retired"] is False

    second = duel.opponent.post(f"/questions/{played.id}/report", json={"reason": "ambiguous"})
    assert second.json()["question_retired"] is True

    session.expire_all()
    assert session.get(Question, played.id).retired_at is not None


def test_typos_alone_never_retire_a_question(session, duel, played, settings_override):
    """A misspelling is worth knowing about but is no reason to pull the question."""
    settings_override(question_report_retire_threshold=2)
    duel.challenger.post(f"/questions/{played.id}/report", json={"reason": "typo"})
    duel.opponent.post(f"/questions/{played.id}/report", json={"reason": "typo"})

    session.expire_all()
    assert session.get(Question, played.id).retired_at is None


def test_retired_questions_are_not_dealt_into_new_rounds(session):
    pool = make_questions_for_category(session, Category.PSALMS_PRAYERS, 4)
    retired = pool[0]
    retired.retired_at = utcnow()
    session.add(retired)
    session.commit()

    for _ in range(10):
        picked = select_questions_for_round(session, Category.PSALMS_PRAYERS, 1000.0, count=3)
        assert retired.id not in {q.id for q in picked}


def test_a_retired_question_does_not_break_a_duel_in_progress(session, duel, settings_override):
    """Retirement affects future deals only — a round already dealt stays playable."""
    settings_override(question_report_retire_threshold=1)
    make_questions_for_category(session, Category.SYMBOLS_CUSTOMS, 3)
    round_id = duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds", json={"category": "symbols_customs"}
    ).json()["round_id"]

    shown = duel.challenger.get(f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1").json()
    duel.challenger.post(
        f"/duels/{duel.duel_id}/rounds/{round_id}/questions/1/answer",
        json={"selected_choice_index": 0},
    )
    reported = duel.challenger.post(
        f"/questions/{shown['question_id']}/report", json={"reason": "wrong_answer"}
    )
    assert reported.json()["question_retired"] is True

    # The rest of the round still plays out.
    for position in (2, 3):
        assert (
            duel.challenger.get(
                f"/duels/{duel.duel_id}/rounds/{round_id}/questions/{position}"
            ).status_code
            == 200
        )
        assert (
            duel.challenger.post(
                f"/duels/{duel.duel_id}/rounds/{round_id}/questions/{position}/answer",
                json={"selected_choice_index": 0},
            ).status_code
            == 200
        )
    answer_all_questions(duel.opponent, duel.duel_id, round_id)


def test_restore_puts_a_question_back_and_closes_its_reports(session, duel, played,
                                                             settings_override):
    settings_override(question_report_retire_threshold=1)
    duel.challenger.post(f"/questions/{played.id}/report", json={"reason": "wrong_answer"})
    session.expire_all()

    question = session.get(Question, played.id)
    restore(session, question)

    assert question.retired_at is None
    assert all(r.status == ReportStatus.DISMISSED for r in session.exec(select(QuestionReport)))


def test_resolve_closes_open_reports(session, duel, played):
    duel.challenger.post(f"/questions/{played.id}/report", json={"reason": "typo"})
    closed = resolve(session, played.id, ReportStatus.RESOLVED)

    assert closed == 1
    assert session.exec(select(QuestionReport)).one().status == ReportStatus.RESOLVED


def test_note_length_is_capped(duel, played):
    resp = duel.challenger.post(
        f"/questions/{played.id}/report", json={"reason": "other", "note": "x" * 5000}
    )
    assert resp.status_code == 422


def test_reporting_works_without_a_note(session, duel, played):
    resp = duel.challenger.post(f"/questions/{played.id}/report", json={"reason": "ambiguous"})
    assert resp.status_code == 201
    assert session.exec(select(QuestionReport)).one().note is None


def test_question_report_endpoint_ignores_unplayed_questions_of_other_categories(
    session, duel, played
):
    other = make_question(session, Category.FAITH_POP_CULTURE, prompt="Nie gespielt")
    assert (
        duel.challenger.post(f"/questions/{other.id}/report", json={"reason": "typo"}).status_code
        == 403
    )
