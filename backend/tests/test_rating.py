import json

from app.models.domain import Category, Player, Question
from app.services.rating import RANK_THRESHOLDS, rank_for_rating, update_ratings_after_answer


def _player(rating: float) -> Player:
    return Player(display_name="P", email=f"p-{rating}@test.local", rating=rating)


def _question(rating: float) -> Question:
    return Question(
        category=Category.HISTORY,
        prompt="?",
        choices=json.dumps(["A", "B", "C", "D"]),
        correct_choice_index=0,
        rating=rating,
    )


def test_correct_answer_raises_player_rating_and_lowers_question_rating():
    player = _player(1000.0)
    question = _question(1000.0)

    update_ratings_after_answer(player, question, is_correct=True)

    assert player.rating > 1000.0
    assert question.rating < 1000.0


def test_incorrect_answer_lowers_player_rating_and_raises_question_rating():
    player = _player(1000.0)
    question = _question(1000.0)

    update_ratings_after_answer(player, question, is_correct=False)

    assert player.rating < 1000.0
    assert question.rating > 1000.0


def test_upset_moves_player_rating_more_than_expected_win():
    favorite = _player(1300.0)
    easy_question = _question(900.0)
    favorite_gain = favorite.rating
    update_ratings_after_answer(favorite, easy_question, is_correct=True)
    favorite_gain = favorite.rating - favorite_gain

    underdog = _player(900.0)
    hard_question = _question(1300.0)
    underdog_gain = underdog.rating
    update_ratings_after_answer(underdog, hard_question, is_correct=True)
    underdog_gain = underdog.rating - underdog_gain

    # Beating an easy question barely moves the favorite's rating; an underdog
    # pulling off an upset against a hard question gains much more.
    assert 0 < favorite_gain < underdog_gain


def test_rank_for_rating_boundaries():
    assert rank_for_rating(0) == "Ketzer"
    for upper_bound, name in RANK_THRESHOLDS[:-1]:
        assert rank_for_rating(upper_bound - 1) == name
        assert rank_for_rating(upper_bound) != name
    assert rank_for_rating(10_000) == "Apostel"
