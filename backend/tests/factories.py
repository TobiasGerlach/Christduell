import json

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.domain import Category, Player, Question


def make_player(session: Session, display_name: str, email: str, rating: float = 1000.0) -> Player:
    player = Player(display_name=display_name, email=email, rating=rating)
    session.add(player)
    session.commit()
    session.refresh(player)
    return player


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


def make_questions_for_category(session: Session, category: Category, count: int = 3) -> list[Question]:
    """Seeds exactly `count` questions — keeps `select_questions_for_round` deterministic
    (it returns the whole pool when there aren't more questions than requested)."""
    return [
        make_question(session, category, prompt=f"{category.value} question {i}")
        for i in range(count)
    ]


def play_round(
    client: TestClient,
    session: Session,
    duel_id: int,
    picker_id: int,
    responder_id: int,
    category: Category,
    picker_choices: tuple[int | None, int | None, int | None] = (0, 0, 0),
    responder_choices: tuple[int | None, int | None, int | None] = (0, 0, 0),
) -> int:
    """Drives one full round (pick + both players answering all 3 questions) to
    completion via the HTTP API. Questions default to `correct_choice_index=0`,
    so a submitted choice of 0 scores correct and anything else scores wrong —
    giving callers full control over the resulting score / rating movement."""
    make_questions_for_category(session, category, 3)
    pick_resp = client.post(
        f"/duels/{duel_id}/rounds", json={"player_id": picker_id, "category": category.value}
    )
    assert pick_resp.status_code == 201, pick_resp.text
    round_id = pick_resp.json()["round_id"]

    for actor, choices in ((picker_id, picker_choices), (responder_id, responder_choices)):
        for position, choice in zip((1, 2, 3), choices):
            get_resp = client.get(
                f"/duels/{duel_id}/rounds/{round_id}/questions/{position}",
                params={"player_id": actor},
            )
            assert get_resp.status_code == 200, get_resp.text
            answer_resp = client.post(
                f"/duels/{duel_id}/rounds/{round_id}/questions/{position}/answer",
                json={"player_id": actor, "selected_choice_index": choice},
            )
            assert answer_resp.status_code == 200, answer_resp.text

    return round_id
