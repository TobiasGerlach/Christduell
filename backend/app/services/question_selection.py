import random

from sqlmodel import Session, col, func, select

from app.models.domain import Category, Question


def select_questions_for_round(
    session: Session, category: Category, picker_rating: float, count: int = 3
) -> list[Question]:
    """Pick `count` questions from `category` whose rating is closest to the
    picking player's rating.

    Sampling from a wider near-match pool (rather than always taking the exact
    closest) avoids the same questions surfacing repeatedly for players who
    cluster around a rating. This is intentionally isolated/swappable — a
    later phase could plug in a smarter selection strategy without touching
    the duel engine around it.
    """
    questions = list(
        session.exec(
            select(Question).where(
                Question.category == category,
                # Reported-and-retired questions stay in the table for review but
                # are never dealt again.
                Question.retired_at.is_(None),
            )
        )
    )
    if len(questions) <= count:
        return questions

    pool_size = min(len(questions), count * 2)
    closest = sorted(questions, key=lambda q: abs(q.rating - picker_rating))[:pool_size]
    return random.sample(closest, count)


def available_question_count(session: Session, category: Category) -> int:
    """How many questions in this category can still be dealt."""
    statement = (
        select(func.count())
        .select_from(Question)
        .where(Question.category == category, Question.retired_at.is_(None))
    )
    return session.exec(statement).one()


def playable_categories(session: Session, count: int, exclude: set[Category]) -> list[Category]:
    """Categories with enough live questions to fill a round.

    Retirement can empty a category out from under the game, so anything the
    player is offered has to be checked rather than assumed.
    """
    counts = dict(
        session.exec(
            select(Question.category, func.count())
            .where(Question.retired_at.is_(None))
            .group_by(col(Question.category))
        ).all()
    )
    return [
        category
        for category in Category
        if category not in exclude and counts.get(category, 0) >= count
    ]
