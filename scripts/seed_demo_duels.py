#!/usr/bin/env python3
"""Creates duels in every interesting state between the two demo players.

Playing eight rounds by hand just to look at the history screen is a waste of an
evening. This drives the real HTTP API — no direct database writes — so the
duels it leaves behind are indistinguishable from played ones.

    make demo-duels                       # against http://localhost:8000
    BASE_URL=http://localhost:8123 make demo-duels

Afterwards Anna's duel list holds:

  - a finished duel            → open it to check the history screen
  - a duel waiting for Anna    → she picks the category
  - a duel waiting for Tobias  → shows the "opponent's turn" state
  - a fresh challenge from Tobias to Anna → the decline flow
"""

import os
import sys

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
PASSWORD = os.environ.get("SEED_PASSWORD", "christduell-dev")
ANNA = "anna@example.com"
TOBIAS = "tobias@example.com"

TOTAL_ROUNDS = 8
QUESTIONS_PER_ROUND = 3


class Player:
    def __init__(self, client: httpx.Client, email: str) -> None:
        response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
        if response.status_code != 200:
            raise SystemExit(
                f"Could not log in as {email}: {response.status_code} {response.text}\n"
                "Run `make reset-db` first — it creates the demo players."
            )
        body = response.json()
        self.client = client
        self.id = body["player"]["id"]
        self.name = body["player"]["display_name"]
        self.headers = {"Authorization": f"Bearer {body['access_token']}"}

    def get(self, path, **kw):
        return self.client.get(path, headers=self.headers, **kw)

    def post(self, path, **kw):
        return self.client.post(path, headers=self.headers, **kw)


def state(player: Player, duel_id: int) -> dict:
    return player.get(f"/duels/{duel_id}/state").json()


def answer_round(actor: Player, duel_id: int, round_id: int, correct: bool) -> None:
    """Answers all three questions of a round, deliberately right or wrong."""
    for position in range(1, QUESTIONS_PER_ROUND + 1):
        question = actor.get(f"/duels/{duel_id}/rounds/{round_id}/questions/{position}")
        question.raise_for_status()
        # The client is never told the answer key before submitting, so "wrong on
        # purpose" just means picking a different index than a fixed guess.
        choice = 0 if correct else 3
        actor.post(
            f"/duels/{duel_id}/rounds/{round_id}/questions/{position}/answer",
            json={"selected_choice_index": choice},
        ).raise_for_status()


def play_round(picker: Player, responder: Player, duel_id: int, both: bool = True) -> int:
    recommendations = picker.get(f"/duels/{duel_id}/recommendations").json()
    category = recommendations[0]["category"]
    pick = picker.post(f"/duels/{duel_id}/rounds", json={"category": category})
    pick.raise_for_status()
    round_id = pick.json()["round_id"]

    answer_round(picker, duel_id, round_id, correct=True)
    if both:
        answer_round(responder, duel_id, round_id, correct=False)
    return round_id


def new_duel(challenger: Player, opponent: Player) -> int:
    response = challenger.post("/duels", json={"opponent_id": opponent.id})
    response.raise_for_status()
    return response.json()["id"]


def main() -> int:
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)
    try:
        client.get("/health").raise_for_status()
    except Exception:
        raise SystemExit(f"No server at {BASE_URL} — start it with `make backend`.") from None

    anna = Player(client, ANNA)
    tobias = Player(client, TOBIAS)
    print(f"Logged in as {anna.name} (#{anna.id}) and {tobias.name} (#{tobias.id})\n")

    # 1. A finished duel — for the history screen and the end-of-duel state.
    duel_id = new_duel(anna, tobias)
    picker, responder = anna, tobias
    for _ in range(TOTAL_ROUNDS):
        play_round(picker, responder, duel_id)
        picker, responder = responder, picker
    finished = state(anna, duel_id)
    print(
        f"  #{duel_id}  finished          "
        f"{finished['challenger_score']}:{finished['opponent_score']} — open it for the history"
    )

    # 2. Mid-duel, waiting for Anna to pick a category.
    duel_id = new_duel(tobias, anna)
    play_round(tobias, anna, duel_id)
    acting = state(anna, duel_id)["acting_player_id"]
    print(f"  #{duel_id}  Anna picks        (acting player: {acting})")

    # 3. Mid-round, waiting for Tobias to answer — Anna sees "opponent's turn".
    duel_id = new_duel(anna, tobias)
    play_round(anna, tobias, duel_id, both=False)
    print(f"  #{duel_id}  Tobias answers    Anna's list shows the waiting state")

    # 4. An untouched challenge — the decline flow.
    duel_id = new_duel(tobias, anna)
    print(f"  #{duel_id}  fresh challenge   long-press it in Anna's list to decline")

    print(f"\nOpen {BASE_URL.replace('8000', '8081')} and log in as {ANNA} / {PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
