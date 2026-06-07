import random

from sqlmodel import Session, select

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
    questions = list(session.exec(select(Question).where(Question.category == category)))
    if len(questions) <= count:
        return questions

    pool_size = min(len(questions), count * 2)
    closest = sorted(questions, key=lambda q: abs(q.rating - picker_rating))[:pool_size]
    return random.sample(closest, count)
