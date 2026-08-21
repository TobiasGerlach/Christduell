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


# One emoji per rank, shown next to the name everywhere a rank appears. The
# ladder tells a story: lost sheep -> seeker -> dove (conversion) -> fish
# (disciple) -> crown (apostle).
RANK_EMOJIS: dict[str, str] = {
    "Ketzer": "🐑",       # sheep (the lost one)
    "Heide": "🧭",        # compass (still searching)
    "Umgekehrter": "🕊️",  # dove
    "Jünger": "🐟",  # fish
    "Apostel": "👑",      # crown
}


def emoji_for_rank(rank: str) -> str:
    return RANK_EMOJIS.get(rank, "")


# Each rank splits into five divisions, V (entry) up to I (about to rank up),
# league-style. The open-ended outer bands get nominal walls so a division can
# be computed: below 700 stays Ketzer V, above 1650 stays Apostel I.
RANK_DIVISION_BANDS: dict[str, tuple[float, float]] = {
    "Ketzer": (700.0, 900.0),
    "Heide": (900.0, 1050.0),
    "Umgekehrter": (1050.0, 1200.0),
    "Jünger": (1200.0, 1400.0),
    "Apostel": (1400.0, 1650.0),
}

RANK_ORDER = [name for _, name in RANK_THRESHOLDS]


def division_for_rating(rating: float) -> int:
    """5 = just entered the rank, 1 = one step from the next rank."""
    rank = rank_for_rating(rating)
    lower, upper = RANK_DIVISION_BANDS[rank]
    if rating < lower:
        return 5
    if rating >= upper:
        return 1
    fifth = (upper - lower) / 5.0
    return 5 - int((rating - lower) / fifth)


def ladder_step_for_rating(rating: float) -> int:
    """Absolute rung on the whole ladder, 0 (Ketzer V) .. 24 (Apostel I).

    Exists so a client can detect "the player climbed" with a single integer
    comparison instead of re-deriving rank order.
    """
    rank = rank_for_rating(rating)
    return RANK_ORDER.index(rank) * 5 + (5 - division_for_rating(rating))


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
