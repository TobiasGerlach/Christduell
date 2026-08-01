import json
from pathlib import Path

from sqlmodel import Session, select

from app.core.security import hash_password
from app.db.session import engine, init_db
from app.models.domain import Category, Player, Question

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Demo accounts for local development. They share one obvious password so both
# sides of a duel can be logged into quickly; never seed these in production.
SEED_PASSWORD = "christduell-dev"
SEED_PLAYERS = [
    {"display_name": "Anna", "email": "anna@christduell.test"},
    {"display_name": "Tobias", "email": "tobias@christduell.test"},
]


def _seed_players(session: Session) -> None:
    for data in SEED_PLAYERS:
        existing = session.exec(select(Player).where(Player.email == data["email"])).first()
        if existing is None:
            session.add(
                Player(
                    display_name=data["display_name"],
                    email=data["email"],
                    password_hash=hash_password(SEED_PASSWORD),
                )
            )
        elif existing.password_hash is None:
            # Pre-auth seed rows can't be logged into; give them the demo password.
            existing.password_hash = hash_password(SEED_PASSWORD)
            session.add(existing)
    session.commit()


def _load_question_fixtures() -> list[dict]:
    """Reads every category file under fixtures/questions/.

    One file per category rather than a single list: a few hundred questions in
    one file is not reviewable, and edits to one category stop colliding with
    edits to another.
    """
    entries: list[dict] = []
    for path in sorted((FIXTURES_DIR / "questions").glob("*.json")):
        entries.extend(json.loads(path.read_text(encoding="utf-8")))
    return entries


def _seed_questions(session: Session) -> None:
    entries = _load_question_fixtures()

    for entry in entries:
        category = Category(entry["category"])
        existing = session.exec(
            select(Question).where(
                Question.category == category, Question.prompt == entry["prompt"]
            )
        ).first()
        if existing is not None:
            existing.reference = entry.get("reference")
            existing.explanation = entry.get("explanation")
            session.add(existing)
            continue
        session.add(
            Question(
                category=category,
                prompt=entry["prompt"],
                choices=json.dumps(entry["choices"], ensure_ascii=False),
                correct_choice_index=entry["correct_choice_index"],
                reference=entry.get("reference"),
                explanation=entry.get("explanation"),
                rating=entry.get("rating", 1000.0),
            )
        )
    session.commit()


def seed() -> None:
    init_db()
    with Session(engine) as session:
        _seed_players(session)
        _seed_questions(session)
    print(f"Seeded {len(_load_question_fixtures())} questions.")
    print(
        "Seeded demo players:\n"
        + "\n".join(f"  {p['email']} / {SEED_PASSWORD}" for p in SEED_PLAYERS)
    )


if __name__ == "__main__":
    seed()
