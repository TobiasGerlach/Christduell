from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentPlayer
from app.core.time import utcnow
from app.db.session import SessionDep
from app.models.domain import (
    QuestionnaireType,
    ResearchConsent,
    SubscriptionTier,
)
from app.services.research import (
    GAMES_REQUIRED_BEFORE_QUESTIONNAIRE,
    create_or_resume_completion,
    get_active_consent,
    get_consent,
    get_due_questionnaire,
    get_finished_duel_count,
    load_questionnaire_definition,
    mark_completion_done,
    save_answers,
)

router = APIRouter(prefix="/research", tags=["research"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ConsentRequest(BaseModel):
    # Consent to basic research participation (faith background, etc.)
    general_consent: bool
    # Separate explicit opt-in required for special-category health data (ADHD/autism).
    health_data_consent: bool = False
    consent_version: str = "1.0"


class ConsentStatus(BaseModel):
    consented: bool
    health_data_consented: bool
    research_tier: bool  # True = on research tier (questionnaires apply)
    games_played: int
    games_required: int
    withdrawn_at: datetime | None


class AnswerSubmitRequest(BaseModel):
    # Flat dict: question_key → response value (string, int, or list[str])
    answers: dict[str, object]
    # Set to True on the final submission to mark the questionnaire complete.
    finished: bool = False


class QuestionnaireStatusResponse(BaseModel):
    due_questionnaire: QuestionnaireType | None
    questionnaire_definition: dict | None


# ---------------------------------------------------------------------------
# Consent endpoints
# ---------------------------------------------------------------------------


@router.post("/consent", response_model=ConsentStatus, status_code=201)
def give_consent(
    payload: ConsentRequest, player: CurrentPlayer, session: SessionDep
) -> ConsentStatus:
    if not payload.general_consent:
        raise HTTPException(status_code=400, detail="general_consent must be true to participate")

    existing = get_consent(session, player.id)
    if existing and existing.withdrawn_at is None:
        # Update health data consent if it changed.
        if payload.health_data_consent and not existing.health_data_consent:
            existing.health_data_consent = True
            session.add(existing)
            session.commit()
            session.refresh(existing)
        consent = existing
    elif existing and existing.withdrawn_at is not None:
        # Re-consent after withdrawal: clear the withdrawal timestamp.
        existing.withdrawn_at = None
        existing.consented_at = utcnow()
        existing.health_data_consent = payload.health_data_consent
        existing.consent_version = payload.consent_version
        session.add(existing)
        session.commit()
        session.refresh(existing)
        consent = existing
    else:
        consent = ResearchConsent(
            player_id=player.id,
            health_data_consent=payload.health_data_consent,
            consent_version=payload.consent_version,
        )
        session.add(consent)
        session.commit()
        session.refresh(consent)

    games = get_finished_duel_count(session, player.id)
    return ConsentStatus(
        consented=True,
        health_data_consented=consent.health_data_consent,
        research_tier=player.subscription_tier == SubscriptionTier.RESEARCH,
        games_played=games,
        games_required=GAMES_REQUIRED_BEFORE_QUESTIONNAIRE,
        withdrawn_at=None,
    )


@router.get("/consent", response_model=ConsentStatus)
def get_consent_status(player: CurrentPlayer, session: SessionDep) -> ConsentStatus:
    consent = get_consent(session, player.id)
    games = get_finished_duel_count(session, player.id)

    return ConsentStatus(
        consented=consent is not None and consent.withdrawn_at is None,
        health_data_consented=consent.health_data_consent if consent else False,
        research_tier=player.subscription_tier == SubscriptionTier.RESEARCH,
        games_played=games,
        games_required=GAMES_REQUIRED_BEFORE_QUESTIONNAIRE,
        withdrawn_at=consent.withdrawn_at if consent else None,
    )


@router.delete("/consent", status_code=204)
def withdraw_consent(player: CurrentPlayer, session: SessionDep) -> None:
    """
    GDPR right to withdraw. Severs the link between the player's identity and
    their pseudonymous research UUID. Existing questionnaire answers are retained
    but become truly anonymous (unlinked from any player).
    """
    consent = get_active_consent(session, player.id)
    if consent is None:
        raise HTTPException(status_code=404, detail="No active consent found")
    consent.withdrawn_at = utcnow()
    session.add(consent)
    session.commit()


# ---------------------------------------------------------------------------
# Questionnaire endpoints
# ---------------------------------------------------------------------------


@router.get("/questionnaire/current", response_model=QuestionnaireStatusResponse)
def get_current_questionnaire(
    player: CurrentPlayer, session: SessionDep
) -> QuestionnaireStatusResponse:
    """Returns the questionnaire the player is currently due to complete, with its definition."""
    due = get_due_questionnaire(session, player.id)
    definition = load_questionnaire_definition(due) if due else None

    return QuestionnaireStatusResponse(
        due_questionnaire=due,
        questionnaire_definition=definition,
    )


@router.post("/questionnaire/{questionnaire_type}/answers", status_code=200)
def submit_answers(
    questionnaire_type: QuestionnaireType,
    payload: AnswerSubmitRequest,
    player: CurrentPlayer,
    session: SessionDep,
) -> dict:
    """
    Submit answers for a questionnaire. Can be called multiple times (supports
    saving progress mid-way). Set finished=True on the final call to mark it
    complete and unlock the next questionnaire after the waiting period.
    """
    consent = get_active_consent(session, player.id)
    if consent is None:
        raise HTTPException(status_code=403, detail="Research consent required")

    # Verify this questionnaire is actually due.
    due = get_due_questionnaire(session, player.id)
    if due != questionnaire_type:
        raise HTTPException(
            status_code=409,
            detail=f"Questionnaire '{questionnaire_type}' is not currently due for this player",
        )

    completion = create_or_resume_completion(session, consent.research_uuid, questionnaire_type)
    save_answers(session, completion, payload.answers)

    if payload.finished:
        mark_completion_done(session, completion)
        return {"status": "completed"}

    return {"status": "saved"}
