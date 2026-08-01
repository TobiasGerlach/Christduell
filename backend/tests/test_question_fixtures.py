"""Guards the question bank itself.

Content is authored by hand in JSON, so the failure modes are content-shaped: a
category that runs dry mid-duel, a copied question, an answer index pointing at
nothing. Cheaper to catch here than in a live duel.
"""

import json
from collections import Counter

import pytest
from sqlmodel import Session, select

from app.db.seed import _load_question_fixtures, _seed_questions
from app.models.domain import Category, Question
from app.services.duel_state import QUESTIONS_PER_ROUND, TOTAL_ROUNDS

FIXTURES = _load_question_fixtures()

# A duel uses one category per round and draws QUESTIONS_PER_ROUND from it, so
# this is the hard floor. The comfortable target is far higher — see todos.md.
MINIMUM_PER_CATEGORY = QUESTIONS_PER_ROUND


def by_category() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for entry in FIXTURES:
        grouped.setdefault(entry["category"], []).append(entry)
    return grouped


def test_every_category_has_questions():
    grouped = by_category()
    missing = [category.value for category in Category if category.value not in grouped]
    assert missing == [], f"categories without any questions: {missing}"


@pytest.mark.parametrize("category", [c.value for c in Category])
def test_category_can_fill_a_whole_duel(category):
    """Eight rounds each use a different category, so every one must be playable."""
    count = len(by_category().get(category, []))
    assert count >= MINIMUM_PER_CATEGORY, f"{category} has only {count} questions"


def test_enough_categories_exist_for_a_full_duel():
    assert len(by_category()) >= TOTAL_ROUNDS


@pytest.mark.parametrize("entry", FIXTURES, ids=lambda e: e["prompt"][:60])
def test_question_is_well_formed(entry):
    assert entry["prompt"].strip(), "empty prompt"
    assert len(entry["choices"]) == 4, "expected exactly four choices"
    assert len(set(entry["choices"])) == 4, "choices must be distinct"
    assert all(choice.strip() for choice in entry["choices"]), "empty choice"
    assert 0 <= entry["correct_choice_index"] < len(entry["choices"])
    assert entry["category"] in {c.value for c in Category}
    # Seeded difficulty; Elo takes over from here.
    assert 700 <= entry.get("rating", 1000) <= 1300


def test_no_duplicate_prompts_anywhere():
    prompts = [entry["prompt"] for entry in FIXTURES]
    duplicates = {p for p in prompts if prompts.count(p) > 1}
    assert duplicates == set(), f"duplicate prompts: {duplicates}"


def test_correct_answers_are_spread_across_all_four_positions():
    """A quiz whose answer is usually A can be won by tapping A.

    The first authored draft had 88 % of answers in position 0 — the fixtures are
    deliberately shuffled, and this keeps them that way as questions get added.
    """
    positions = Counter(entry["correct_choice_index"] for entry in FIXTURES)
    assert set(positions) == {0, 1, 2, 3}, "some position is never the answer"

    for position, count in positions.items():
        share = count / len(FIXTURES)
        assert 0.15 <= share <= 0.35, f"position {position} holds {share:.0%} of the answers"


def test_seeding_is_idempotent(session: Session):
    _seed_questions(session)
    after_first = len(list(session.exec(select(Question))))
    _seed_questions(session)
    after_second = len(list(session.exec(select(Question))))

    assert after_first == len(FIXTURES)
    assert after_second == after_first, "re-seeding duplicated questions"


def test_seeding_stores_choices_reference_and_explanation(session: Session):
    _seed_questions(session)
    sourced = session.exec(select(Question).where(Question.reference.is_not(None))).first()

    assert sourced is not None, "no question carries a reference"
    assert len(json.loads(sourced.choices)) == 4
    assert sourced.explanation
