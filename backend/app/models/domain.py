import uuid
from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel, UniqueConstraint

from app.core.time import utcnow


class DuelStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    FINISHED = "finished"
    DECLINED = "declined"


class Category(StrEnum):
    OLD_TESTAMENT = "old_testament"
    NEW_TESTAMENT = "new_testament"
    BEYOND_THE_HORIZON = "beyond_the_horizon"
    ANCIENT_LANGUAGES = "ancient_languages"
    HISTORY = "history"
    JESUS_TODAY = "jesus_today"
    CHURCH_YEAR_FESTIVALS = "church_year_festivals"
    PARABLES_MIRACLES = "parables_miracles"
    PSALMS_PRAYERS = "psalms_prayers"
    SYMBOLS_CUSTOMS = "symbols_customs"
    SAINTS_ROLE_MODELS = "saints_role_models"
    FACTS_NUMBERS_DATES = "facts_numbers_dates"
    FAITH_POP_CULTURE = "faith_pop_culture"


class SubscriptionTier(StrEnum):
    RESEARCH = "research"  # free, participates in monthly questionnaires
    PAID = "paid"          # €5/month, no questionnaires required


class WebPushSubscription(SQLModel, table=True):
    """One browser's Web Push endpoint. A player can have several (phone +
    laptop); an endpoint identifies a browser profile, not a person, so it
    moves to whoever is signed in on that browser."""

    id: int | None = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="player.id", index=True)
    endpoint: str = Field(unique=True, index=True)
    p256dh: str
    auth: str
    created_at: datetime = Field(default_factory=utcnow)


class Player(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    display_name: str
    # Stored lower-cased so lookups and the unique constraint are case-insensitive.
    email: str = Field(unique=True, index=True)
    # None means "account exists but has no password yet" — such an account can
    # never be logged into (used by legacy/seeded rows).
    password_hash: str | None = None
    push_token: str | None = None
    rating: float = Field(default=1000.0)
    subscription_tier: SubscriptionTier = Field(default=SubscriptionTier.RESEARCH)
    subscription_valid_until: datetime | None = None
    # Set when the player cancels: access runs until subscription_valid_until,
    # then the nightly downgrade puts them back on the research tier.
    subscription_cancel_at_period_end: bool = Field(default=False)
    billing_customer_id: str | None = Field(default=None, index=True)
    billing_subscription_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    # When the player confirmed being 16+ (or having parental consent) at
    # registration — GDPR Art. 8 accountability. Null on rows that predate it.
    min_age_confirmed_at: datetime | None = None
    # Account deletion is a soft delete: PII is scrubbed in place and login is
    # blocked, but the row survives so past duels keep referential integrity.
    deleted_at: datetime | None = None


class Question(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    category: Category
    prompt: str
    choices: str  # JSON-encoded list[str]
    correct_choice_index: int
    # Shown once the answer is revealed — the app is meant to teach, and a
    # citation is what settles a dispute about an answer key.
    reference: str | None = None    # e.g. "Gen 6,14"
    explanation: str | None = None  # one sentence
    # Seeded per authored difficulty (~850 easy / 1000 medium / 1150 hard) and
    # then adjusted by the Elo update on every answer.
    rating: float = Field(default=1000.0)
    # Set when enough players report the question — it stops being dealt into
    # new rounds without being deleted, so the reports stay reviewable.
    retired_at: datetime | None = None


class Duel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    challenger_id: int = Field(foreign_key="player.id")
    opponent_id: int = Field(foreign_key="player.id")
    status: DuelStatus = Field(default=DuelStatus.PENDING)
    created_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


class DuelRound(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("duel_id", "sequence", name="uq_duel_round_sequence"),
        UniqueConstraint("duel_id", "category", name="uq_duel_round_category"),
    )

    id: int | None = Field(default=None, primary_key=True)
    duel_id: int = Field(foreign_key="duel.id", index=True)
    sequence: int
    category: Category
    picked_by_id: int = Field(foreign_key="player.id")
    first_responder_id: int = Field(foreign_key="player.id")
    second_responder_id: int = Field(foreign_key="player.id")
    first_responder_completed_at: datetime | None = None
    second_responder_completed_at: datetime | None = None
    revealed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class DuelRoundQuestion(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("round_id", "position", name="uq_round_question_position"),)

    id: int | None = Field(default=None, primary_key=True)
    round_id: int = Field(foreign_key="duelround.id", index=True)
    question_id: int = Field(foreign_key="question.id")
    position: int


class DuelAnswer(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("round_id", "question_id", "player_id", name="uq_duel_answer_identity"),
    )

    id: int | None = Field(default=None, primary_key=True)
    round_id: int = Field(foreign_key="duelround.id", index=True)
    question_id: int = Field(foreign_key="question.id")
    player_id: int = Field(foreign_key="player.id", index=True)
    shown_at: datetime = Field(default_factory=utcnow)
    answered_at: datetime | None = None
    selected_choice_index: int | None = None
    is_correct: bool | None = None
    is_timeout: bool = Field(default=False)
    response_time_ms: int | None = None


class ReportReason(StrEnum):
    WRONG_ANSWER = "wrong_answer"      # the marked answer is not correct
    AMBIGUOUS = "ambiguous"            # more than one answer works
    TYPO = "typo"                      # spelling or grammar
    INAPPROPRIATE = "inappropriate"    # offensive or out of place
    OTHER = "other"


class ReportStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"      # the question was fixed
    DISMISSED = "dismissed"    # the question was fine


class QuestionReport(SQLModel, table=True):
    """A player's complaint about a question.

    One report per player per question — a single annoyed person cannot retire a
    question by reporting it repeatedly.
    """

    __table_args__ = (
        UniqueConstraint("question_id", "player_id", name="uq_report_per_player"),
    )

    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    player_id: int = Field(foreign_key="player.id", index=True)
    reason: ReportReason
    note: str | None = None
    status: ReportStatus = Field(default=ReportStatus.OPEN, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None


# ---------------------------------------------------------------------------
# Research / questionnaire models
# ---------------------------------------------------------------------------


class QuestionnaireType(StrEnum):
    FAITH_BACKGROUND = "faith_background"  # month 1: demographics, confession, hermeneutics
    ADHD_SCREENER = "adhd_screener"        # month 2: ASRS v1.1
    AUTISM_SCREENER = "autism_screener"    # month 3: AQ-50


class ResearchConsent(SQLModel, table=True):
    """
    Bridges a player's real identity to a pseudonymous research UUID.
    The research UUID is the only identifier stored alongside questionnaire
    answers — the link here can be severed (withdrawn_at set) to honour
    right-to-erasure without destroying already-anonymised data.
    """
    player_id: int = Field(foreign_key="player.id", primary_key=True)
    # Opaque UUID used in all research tables; never exposed alongside PII.
    research_uuid: str = Field(
        default_factory=lambda: str(uuid.uuid4()), unique=True, index=True
    )
    consented_at: datetime = Field(default_factory=utcnow)
    # Increment when consent text changes so we know which version was accepted.
    consent_version: str = Field(default="1.0")
    health_data_consent: bool = Field(default=False)  # explicit opt-in for ADHD/autism data
    withdrawn_at: datetime | None = None


class QuestionnaireCompletion(SQLModel, table=True):
    """One record per (participant, questionnaire) pair."""
    id: int | None = Field(default=None, primary_key=True)
    # Linked to ResearchConsent.research_uuid, NOT to Player.id.
    research_uuid: str = Field(index=True)
    questionnaire_type: QuestionnaireType
    started_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None


class QuestionnaireAnswer(SQLModel, table=True):
    """Individual question responses, stored only under the pseudonymous UUID."""
    __table_args__ = (
        UniqueConstraint("completion_id", "question_key", name="uq_answer_per_question"),
    )

    id: int | None = Field(default=None, primary_key=True)
    completion_id: int = Field(foreign_key="questionnairecompletion.id", index=True)
    question_key: str   # e.g. "denomination", "asrs_q1"
    response_value: str  # JSON-encoded — string, int, list[str], etc.
