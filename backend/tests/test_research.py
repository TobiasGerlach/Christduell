from datetime import timedelta

import pytest

from app.core.time import utcnow
from app.models.domain import (
    Duel,
    DuelStatus,
    QuestionnaireCompletion,
    QuestionnaireType,
    ResearchConsent,
    SubscriptionTier,
)
from app.services.research import (
    DAYS_BETWEEN_QUESTIONNAIRES,
    GAMES_REQUIRED_BEFORE_QUESTIONNAIRE,
    get_due_questionnaire,
)
from tests.factories import make_player, make_player_client


def make_finished_duels(session, player_id: int, count: int) -> None:
    """Inserts `count` FINISHED duels involving the player (as challenger)."""
    for _ in range(count):
        session.add(
            Duel(
                challenger_id=player_id,
                opponent_id=player_id,
                status=DuelStatus.FINISHED,
                finished_at=utcnow(),
            )
        )
    session.commit()


@pytest.fixture(name="participant")
def participant_fixture(client, session):
    return make_player_client(session, client, "P", "p@example.com")


# ---------------------------------------------------------------------------
# Consent endpoints
# ---------------------------------------------------------------------------


def test_consent_requires_general_consent(participant):
    resp = participant.post("/research/consent", json={"general_consent": False})
    assert resp.status_code == 400


def test_consent_requires_authentication(client):
    resp = client.post("/research/consent", json={"general_consent": True})
    assert resp.status_code == 401


def test_consent_creates_pseudonymous_record(session, participant):
    resp = participant.post("/research/consent", json={"general_consent": True})
    assert resp.status_code == 201
    body = resp.json()
    assert body["consented"] is True
    assert body["health_data_consented"] is False
    assert body["research_tier"] is True
    assert body["games_required"] == GAMES_REQUIRED_BEFORE_QUESTIONNAIRE

    consent = session.get(ResearchConsent, participant.id)
    assert consent is not None
    assert consent.research_uuid  # opaque pseudonym generated


def test_consent_status_reflects_games_played(session, participant):
    participant.post("/research/consent", json={"general_consent": True})
    make_finished_duels(session, participant.id, 3)

    resp = participant.get("/research/consent")
    assert resp.status_code == 200
    assert resp.json()["games_played"] == 3


def test_withdraw_then_reconsent_keeps_same_uuid(session, participant):
    participant.post("/research/consent", json={"general_consent": True})
    original_uuid = session.get(ResearchConsent, participant.id).research_uuid

    withdraw = participant.delete("/research/consent")
    assert withdraw.status_code == 204

    status = participant.get("/research/consent").json()
    assert status["consented"] is False
    assert status["withdrawn_at"] is not None

    # Re-consent clears the withdrawal but preserves the pseudonymous UUID.
    participant.post("/research/consent", json={"general_consent": True})
    session.expire_all()
    reconsent = session.get(ResearchConsent, participant.id)
    assert reconsent.withdrawn_at is None
    assert reconsent.research_uuid == original_uuid


def test_withdraw_without_consent_404(participant):
    resp = participant.delete("/research/consent")
    assert resp.status_code == 404


def test_consent_is_scoped_to_the_authenticated_player(client, session, participant):
    """One player's consent must never create or read another player's record."""
    other = make_player_client(session, client, "Other", "other@example.com")
    participant.post("/research/consent", json={"general_consent": True})

    assert other.get("/research/consent").json()["consented"] is False
    assert session.get(ResearchConsent, other.id) is None


# ---------------------------------------------------------------------------
# Questionnaire gating rules (service layer)
# ---------------------------------------------------------------------------


def test_no_questionnaire_without_consent(session):
    player = make_player(session, "P", "p@example.com")
    make_finished_duels(session, player.id, GAMES_REQUIRED_BEFORE_QUESTIONNAIRE)
    assert get_due_questionnaire(session, player.id) is None


def test_no_questionnaire_before_minimum_games(session):
    player = make_player(session, "P", "p@example.com")
    session.add(ResearchConsent(player_id=player.id))
    make_finished_duels(session, player.id, GAMES_REQUIRED_BEFORE_QUESTIONNAIRE - 1)
    session.commit()
    assert get_due_questionnaire(session, player.id) is None


def test_active_subscribers_never_get_questionnaires(session):
    player = make_player(session, "P", "p@example.com")
    player.subscription_tier = SubscriptionTier.PAID
    player.subscription_valid_until = utcnow() + timedelta(days=20)
    session.add(player)
    session.add(ResearchConsent(player_id=player.id))
    make_finished_duels(session, player.id, GAMES_REQUIRED_BEFORE_QUESTIONNAIRE)
    session.commit()
    assert get_due_questionnaire(session, player.id) is None


def test_lapsed_subscribers_owe_questionnaires_again(session):
    """The stored tier is not entitlement: a subscription whose paid period ran
    out still counts as free, even before the nightly downgrade notices."""
    player = make_player(session, "P", "p@example.com")
    player.subscription_tier = SubscriptionTier.PAID
    player.subscription_valid_until = utcnow() - timedelta(days=1)
    session.add(player)
    session.add(ResearchConsent(player_id=player.id))
    make_finished_duels(session, player.id, GAMES_REQUIRED_BEFORE_QUESTIONNAIRE)
    session.commit()

    assert get_due_questionnaire(session, player.id) == QuestionnaireType.FAITH_BACKGROUND


def test_paid_tier_without_a_paid_through_date_is_not_entitlement(session):
    player = make_player(session, "P", "p@example.com")
    player.subscription_tier = SubscriptionTier.PAID
    player.subscription_valid_until = None
    session.add(player)
    session.add(ResearchConsent(player_id=player.id))
    make_finished_duels(session, player.id, GAMES_REQUIRED_BEFORE_QUESTIONNAIRE)
    session.commit()

    assert get_due_questionnaire(session, player.id) is not None


def test_first_questionnaire_due_when_eligible(session):
    player = make_player(session, "P", "p@example.com")
    session.add(ResearchConsent(player_id=player.id))
    make_finished_duels(session, player.id, GAMES_REQUIRED_BEFORE_QUESTIONNAIRE)
    session.commit()
    assert get_due_questionnaire(session, player.id) == QuestionnaireType.FAITH_BACKGROUND


def test_health_questionnaire_blocked_without_health_consent(session):
    player = make_player(session, "P", "p@example.com")
    consent = ResearchConsent(player_id=player.id, health_data_consent=False)
    session.add(consent)
    make_finished_duels(session, player.id, GAMES_REQUIRED_BEFORE_QUESTIONNAIRE)
    session.commit()

    # Complete month 1 well in the past so month 2 (ADHD) would otherwise be due.
    session.add(
        QuestionnaireCompletion(
            research_uuid=consent.research_uuid,
            questionnaire_type=QuestionnaireType.FAITH_BACKGROUND,
            completed_at=utcnow() - timedelta(days=DAYS_BETWEEN_QUESTIONNAIRES + 1),
        )
    )
    session.commit()
    assert get_due_questionnaire(session, player.id) is None


def test_next_questionnaire_respects_waiting_period(session):
    player = make_player(session, "P", "p@example.com")
    consent = ResearchConsent(player_id=player.id, health_data_consent=True)
    session.add(consent)
    make_finished_duels(session, player.id, GAMES_REQUIRED_BEFORE_QUESTIONNAIRE)
    session.commit()

    # Month 1 finished only recently -> month 2 is not due yet.
    recent = QuestionnaireCompletion(
        research_uuid=consent.research_uuid,
        questionnaire_type=QuestionnaireType.FAITH_BACKGROUND,
        completed_at=utcnow() - timedelta(days=1),
    )
    session.add(recent)
    session.commit()
    assert get_due_questionnaire(session, player.id) is None

    # Push it past the waiting period -> month 2 (ADHD) unlocks.
    recent.completed_at = utcnow() - timedelta(days=DAYS_BETWEEN_QUESTIONNAIRES + 1)
    session.add(recent)
    session.commit()
    assert get_due_questionnaire(session, player.id) == QuestionnaireType.ADHD_SCREENER


# ---------------------------------------------------------------------------
# Answer submission flow
# ---------------------------------------------------------------------------


@pytest.fixture(name="eligible")
def eligible_fixture(client, session):
    participant = make_player_client(session, client, "P", "p@example.com")
    session.add(ResearchConsent(player_id=participant.id))
    make_finished_duels(session, participant.id, GAMES_REQUIRED_BEFORE_QUESTIONNAIRE)
    session.commit()
    return participant


def test_submit_answers_requires_consent(participant):
    resp = participant.post(
        "/research/questionnaire/faith_background/answers",
        json={"answers": {"age_range": "25–34"}},
    )
    assert resp.status_code == 403


def test_submit_answers_rejects_not_due_questionnaire(eligible):
    # ADHD is not due until faith_background is finished.
    resp = eligible.post(
        "/research/questionnaire/adhd_screener/answers", json={"answers": {"asrs_a1": "Oft"}}
    )
    assert resp.status_code == 409


def test_submit_and_finish_questionnaire(eligible):
    # Save progress.
    save = eligible.post(
        "/research/questionnaire/faith_background/answers",
        json={"answers": {"age_range": "25–34"}},
    )
    assert save.status_code == 200
    assert save.json()["status"] == "saved"

    # Finish it.
    finish = eligible.post(
        "/research/questionnaire/faith_background/answers",
        json={"answers": {"gender": "Weiblich"}, "finished": True},
    )
    assert finish.status_code == 200
    assert finish.json()["status"] == "completed"

    # Completed -> no longer due.
    current = eligible.get("/research/questionnaire/current")
    assert current.json()["due_questionnaire"] is None


def test_current_questionnaire_returns_definition(eligible):
    resp = eligible.get("/research/questionnaire/current")
    assert resp.status_code == 200
    body = resp.json()
    assert body["due_questionnaire"] == QuestionnaireType.FAITH_BACKGROUND.value
    assert body["questionnaire_definition"]["type"] == QuestionnaireType.FAITH_BACKGROUND.value


def test_answers_must_belong_to_the_questionnaire(eligible):
    """Without this check any client could write arbitrary rows into the dataset."""
    resp = eligible.post(
        "/research/questionnaire/faith_background/answers",
        json={"answers": {"age_range": "25–34", "erfundener_schluessel": "x"}},
    )
    assert resp.status_code == 422
    assert "erfundener_schluessel" in resp.text
