import json
from pathlib import Path

from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models.domain import Category, Player, Question

FIXTURES_DIR = Path(__file__).parent / "fixtures"

SEED_PLAYERS = [
    {"display_name": "Anna", "email": "anna@christduell.test"},
    {"display_name": "Tobias", "email": "tobias@christduell.test"},
]


def _seed_players(session: Session) -> None:
    for data in SEED_PLAYERS:
        existing = session.exec(select(Player).where(Player.email == data["email"])).first()
        if existing is None:
            session.add(Player(display_name=data["display_name"], email=data["email"]))
    session.commit()


def _seed_questions(session: Session) -> None:
    entries = json.loads((FIXTURES_DIR / "questions.json").read_text(encoding="utf-8"))

    for entry in entries:
        category = Category(entry["category"])
        existing = session.exec(
            select(Question).where(Question.category == category, Question.prompt == entry["prompt"])
        ).first()
        if existing is not None:
            continue
        session.add(
            Question(
                category=category,
                prompt=entry["prompt"],
                choices=json.dumps(entry["choices"], ensure_ascii=False),
                correct_choice_index=entry["correct_choice_index"],
                rating=entry.get("rating", 1000.0),
            )
        )
    session.commit()


def seed() -> None:
    init_db()
    with Session(engine) as session:
        _seed_players(session)
        _seed_questions(session)


if __name__ == "__main__":
    seed()
