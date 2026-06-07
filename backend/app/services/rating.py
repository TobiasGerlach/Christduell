from app.models.domain import Player, Question

K_PLAYER = 32.0
K_QUESTION = 16.0

# Display-only derived layer. Selection always uses the continuous rating —
# these thresholds are tunable once real rating distributions are observed.
RANK_THRESHOLDS: list[tuple[float, str]] = [
    (900.0, "Ketzer"),
    (1050.0, "Heide"),
    (1200.0, "Umgekehrter"),
    (1400.0, "Jünger"),
    (float("inf"), "Apostel"),
]


def rank_for_rating(rating: float) -> str:
    for upper_bound, name in RANK_THRESHOLDS:
        if rating < upper_bound:
            return name
    return RANK_THRESHOLDS[-1][1]


def update_ratings_after_answer(player: Player, question: Question, is_correct: bool) -> None:
    """Apply a standard Elo update treating the answer as "player vs. question".

    Player rating moves toward the actual outcome; question rating moves the
    opposite way to recalibrate its difficulty estimate (smaller K dampens
    volatility since many players feed a single question's rating).
    """
    expected_correct = 1.0 / (1.0 + 10 ** ((question.rating - player.rating) / 400.0))
    actual = 1.0 if is_correct else 0.0

    player.rating += K_PLAYER * (actual - expected_correct)
    question.rating += K_QUESTION * (expected_correct - actual)
