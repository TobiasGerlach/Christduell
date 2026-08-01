import json
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, func, select

from app.core.time import utcnow
from app.models.domain import (
    Duel,
    DuelStatus,
    Player,
    QuestionnaireAnswer,
    QuestionnaireCompletion,
    QuestionnaireType,
    ResearchConsent,
)
from app.services.subscriptions import is_subscription_active

FIXTURES_DIR = Path(__file__).parent.parent / "db" / "fixtures"

# How many completed duels a player must have before the first questionnaire appears.
GAMES_REQUIRED_BEFORE_QUESTIONNAIRE = 5

# Days between questionnaires.
DAYS_BETWEEN_QUESTIONNAIRES = 30

# Ordered sequence of questionnaires. Month 2 and 3 require health_data_consent.
QUESTIONNAIRE_SEQUENCE = [
    QuestionnaireType.FAITH_BACKGROUND,
    QuestionnaireType.ADHD_SCREENER,
    QuestionnaireType.AUTISM_SCREENER,
]

HEALTH_DATA_QUESTIONNAIRES = {
    QuestionnaireType.ADHD_SCREENER,
    QuestionnaireType.AUTISM_SCREENER,
}


def load_questionnaire_definition(q_type: QuestionnaireType) -> dict:
    mapping = {
        QuestionnaireType.FAITH_BACKGROUND: "questionnaire_faith_background.json",
        QuestionnaireType.ADHD_SCREENER: "questionnaire_adhd_screener.json",
        QuestionnaireType.AUTISM_SCREENER: "questionnaire_autism_screener.json",
    }
    return json.loads((FIXTURES_DIR / mapping[q_type]).read_text(encoding="utf-8"))


def get_finished_duel_count(session: Session, player_id: int) -> int:
    return session.exec(
        select(func.count(Duel.id)).where(
            (Duel.challenger_id == player_id) | (Duel.opponent_id == player_id),
            Duel.status == DuelStatus.FINISHED,
        )
    ).one()


def get_consent(session: Session, player_id: int) -> ResearchConsent | None:
    return session.get(ResearchConsent, player_id)


def get_active_consent(session: Session, player_id: int) -> ResearchConsent | None:
    """Returns consent only if it exists and has not been withdrawn."""
    consent = get_consent(session, player_id)
    if consent and consent.withdrawn_at is None:
        return consent
    return None


def _latest_completion(
    session: Session, research_uuid: str, q_type: QuestionnaireType
) -> QuestionnaireCompletion | None:
    return session.exec(
        select(QuestionnaireCompletion).where(
            QuestionnaireCompletion.research_uuid == research_uuid,
            QuestionnaireCompletion.questionnaire_type == q_type,
            QuestionnaireCompletion.completed_at.is_not(None),
        )
    ).first()


def get_due_questionnaire(
    session: Session, player_id: int
) -> QuestionnaireType | None:
    """
    Returns the next questionnaire that the player is due to complete, or None.

    Rules:
    - Player must have active research consent (not paid tier, not withdrawn).
    - Player must have finished >= GAMES_REQUIRED_BEFORE_QUESTIONNAIRE duels.
    - Questionnaires unlock in sequence; each is separated by DAYS_BETWEEN_QUESTIONNAIRES.
    - Months 2 & 3 require explicit health data consent.
    """
    player = session.get(Player, player_id)
    if player is None:
        return None
    # Entitlement, not the stored tier: a subscription that lapsed before the
    # nightly downgrade ran must not still buy questionnaire-free play.
    if is_subscription_active(player):
        return None

    consent = get_active_consent(session, player_id)
    if consent is None:
        return None

    if get_finished_duel_count(session, player_id) < GAMES_REQUIRED_BEFORE_QUESTIONNAIRE:
        return None

    now = utcnow()
    prev_completed_at: datetime | None = None

    for q_type in QUESTIONNAIRE_SEQUENCE:
        if q_type in HEALTH_DATA_QUESTIONNAIRES and not consent.health_data_consent:
            return None  # health questionnaires require separate explicit consent

        completion = _latest_completion(session, consent.research_uuid, q_type)
        if completion is None:
            # First in sequence: available immediately once prerequisites met.
            # Subsequent: available only after the waiting period.
            if prev_completed_at is None:
                return q_type
            if (now - prev_completed_at).days >= DAYS_BETWEEN_QUESTIONNAIRES:
                return q_type
            return None  # too early for next questionnaire
        prev_completed_at = completion.completed_at

    return None  # all questionnaires completed


def known_question_keys(q_type: QuestionnaireType) -> set[str]:
    """Every question key the given questionnaire actually defines."""
    definition = load_questionnaire_definition(q_type)
    return {
        question["key"]
        for section in definition.get("sections", [])
        for question in section.get("questions", [])
    }


def create_or_resume_completion(
    session: Session, research_uuid: str, q_type: QuestionnaireType
) -> QuestionnaireCompletion:
    """Returns an existing incomplete session or starts a new one."""
    existing = session.exec(
        select(QuestionnaireCompletion).where(
            QuestionnaireCompletion.research_uuid == research_uuid,
            QuestionnaireCompletion.questionnaire_type == q_type,
            QuestionnaireCompletion.completed_at.is_(None),
        )
    ).first()
    if existing:
        return existing

    completion = QuestionnaireCompletion(
        research_uuid=research_uuid,
        questionnaire_type=q_type,
    )
    session.add(completion)
    session.commit()
    session.refresh(completion)
    return completion


def save_answers(
    session: Session,
    completion: QuestionnaireCompletion,
    answers: dict[str, object],
) -> None:
    for key, value in answers.items():
        existing = session.exec(
            select(QuestionnaireAnswer).where(
                QuestionnaireAnswer.completion_id == completion.id,
                QuestionnaireAnswer.question_key == key,
            )
        ).first()
        if existing:
            existing.response_value = json.dumps(value, ensure_ascii=False)
            session.add(existing)
        else:
            session.add(
                QuestionnaireAnswer(
                    completion_id=completion.id,
                    question_key=key,
                    response_value=json.dumps(value, ensure_ascii=False),
                )
            )
    session.commit()


def mark_completion_done(session: Session, completion: QuestionnaireCompletion) -> None:
    completion.completed_at = utcnow()
    session.add(completion)
    session.commit()
