from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel, UniqueConstraint


class DuelStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    FINISHED = "finished"


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


class Player(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    display_name: str
    email: str = Field(unique=True, index=True)
    push_token: str | None = None
    rating: float = Field(default=1000.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Question(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    category: Category
    prompt: str
    choices: str  # JSON-encoded list[str]
    correct_choice_index: int
    rating: float = Field(default=1000.0)


class Duel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    challenger_id: int = Field(foreign_key="player.id")
    opponent_id: int = Field(foreign_key="player.id")
    status: DuelStatus = Field(default=DuelStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
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
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
    shown_at: datetime = Field(default_factory=datetime.utcnow)
    answered_at: datetime | None = None
    selected_choice_index: int | None = None
    is_correct: bool | None = None
    is_timeout: bool = Field(default=False)
    response_time_ms: int | None = None
