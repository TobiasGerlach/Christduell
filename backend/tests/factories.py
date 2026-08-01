import json

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.security import create_access_token, hash_password
from app.models.domain import Category, Player, Question

DEFAULT_PASSWORD = "test-password-123"


class PlayerClient:
    """A TestClient bound to one player's bearer token.

    Every player-scoped endpoint takes its identity from the token, so tests
    talk to the API as a specific person instead of passing player ids around.
    """

    def __init__(self, client: TestClient, player: Player) -> None:
        self._client = client
        self.player = player
        self._headers = {"Authorization": f"Bearer {create_access_token(player.id)}"}

    @property
    def id(self) -> int:
        return self.player.id

    def _with_auth(self, kwargs: dict) -> dict:
        headers = {**self._headers, **(kwargs.pop("headers", None) or {})}
        return {**kwargs, "headers": headers}

    def get(self, url: str, **kwargs):
        return self._client.get(url, **self._with_auth(kwargs))

    def post(self, url: str, **kwargs):
        return self._client.post(url, **self._with_auth(kwargs))

    def patch(self, url: str, **kwargs):
        return self._client.patch(url, **self._with_auth(kwargs))

    def delete(self, url: str, **kwargs):
        return self._client.delete(url, **self._with_auth(kwargs))


def make_player(
    session: Session,
    display_name: str,
    email: str,
    rating: float = 1000.0,
    password: str | None = DEFAULT_PASSWORD,
) -> Player:
    player = Player(
        display_name=display_name,
        email=email.lower(),
        rating=rating,
        password_hash=hash_password(password) if password else None,
    )
    session.add(player)
    session.commit()
    session.refresh(player)
    return player


def make_player_client(
    session: Session, client: TestClient, display_name: str, email: str, rating: float = 1000.0
) -> PlayerClient:
    return PlayerClient(client, make_player(session, display_name, email, rating))


def make_question(
    session: Session,
    category: Category,
    prompt: str,
    correct_choice_index: int = 0,
    rating: float = 1000.0,
) -> Question:
    question = Question(
        category=category,
        prompt=prompt,
        choices=json.dumps(["A", "B", "C", "D"], ensure_ascii=False),
        correct_choice_index=correct_choice_index,
        rating=rating,
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


def make_questions_for_category(
    session: Session, category: Category, count: int = 3
) -> list[Question]:
    """Seeds exactly `count` questions — keeps `select_questions_for_round` deterministic
    (it returns the whole pool when there aren't more questions than requested)."""
    return [
        make_question(session, category, prompt=f"{category.value} question {i}")
        for i in range(count)
    ]


def answer_all_questions(
    actor: PlayerClient,
    duel_id: int,
    round_id: int,
    choices: tuple[int | None, ...] = (0, 0, 0),
) -> None:
    for position, choice in zip((1, 2, 3), choices, strict=True):
        shown = actor.get(f"/duels/{duel_id}/rounds/{round_id}/questions/{position}")
        assert shown.status_code == 200, shown.text
        answered = actor.post(
            f"/duels/{duel_id}/rounds/{round_id}/questions/{position}/answer",
            json={"selected_choice_index": choice},
        )
        assert answered.status_code == 200, answered.text


def play_round(
    session: Session,
    duel_id: int,
    picker: PlayerClient,
    responder: PlayerClient,
    category: Category,
    picker_choices: tuple[int | None, int | None, int | None] = (0, 0, 0),
    responder_choices: tuple[int | None, int | None, int | None] = (0, 0, 0),
) -> int:
    """Drives one full round (pick + both players answering all 3 questions) to
    completion via the HTTP API. Questions default to `correct_choice_index=0`,
    so a submitted choice of 0 scores correct and anything else scores wrong —
    giving callers full control over the resulting score / rating movement."""
    make_questions_for_category(session, category, 3)
    pick_resp = picker.post(f"/duels/{duel_id}/rounds", json={"category": category.value})
    assert pick_resp.status_code == 201, pick_resp.text
    round_id = pick_resp.json()["round_id"]

    answer_all_questions(picker, duel_id, round_id, picker_choices)
    answer_all_questions(responder, duel_id, round_id, responder_choices)

    return round_id
