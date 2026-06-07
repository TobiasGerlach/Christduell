from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class DuelStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    FINISHED = "finished"


class Category(StrEnum):
    OLD_TESTAMENT = "old_testament"
    NEW_TESTAMENT = "new_testament"
    CHURCH_HISTORY = "church_history"
    THEOLOGY = "theology"
    GENERAL = "general"


class Player(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    display_name: str
    email: str = Field(unique=True, index=True)
    push_token: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Question(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    category: Category
    prompt: str
    choices: str  # JSON-encoded list[str]
    correct_choice_index: int


class Duel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    challenger_id: int = Field(foreign_key="player.id")
    opponent_id: int = Field(foreign_key="player.id")
    status: DuelStatus = Field(default=DuelStatus.PENDING)
    challenger_score: int = Field(default=0)
    opponent_score: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
