#!/usr/bin/env python3
"""End-to-end smoke test against a *running* Christduell backend.

Unlike the pytest suite (which drives the app in-process), this exercises the
real HTTP surface of a real server: two accounts register, challenge each other,
play a full eight-round duel, subscribe, and walk the research flow. Use it to
check a local server before a release, and after a deploy against staging.

    uv run --project backend python scripts/smoke_test.py
    BASE_URL=https://christduell-production-api.azurewebsites.net \\
        uv run --project backend python scripts/smoke_test.py

Every account it creates is deleted again at the end, so it is safe to point at
a real environment — but it does write real duels first, so prefer staging.

Exit code 0 means everything passed.
"""

import os
import sys
import time
import uuid

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = float(os.environ.get("TIMEOUT", "20"))
PASSWORD = "smoke-test-password"

TOTAL_ROUNDS = 8
QUESTIONS_PER_ROUND = 3

passed = 0
failed: list[str] = []


def check(description: str, condition: bool, detail: str = "") -> None:
    global passed
    if condition:
        passed += 1
        print(f"  ✓ {description}")
    else:
        failed.append(f"{description} — {detail}" if detail else description)
        print(f"  ✗ {description} {detail}")


class Player:
    """An HTTP client bound to one registered account."""

    def __init__(self, client: httpx.Client, display_name: str) -> None:
        self.client = client
        # example.com is reserved for exactly this; reserved TLDs like .test are
        # rejected by the email validator.
        self.email = f"smoke-{uuid.uuid4().hex[:12]}@example.com"
        response = client.post(
            "/auth/register",
            json={
                "display_name": display_name,
                "email": self.email,
                "password": PASSWORD,
                "min_age_confirmed": True,
            },
        )
        response.raise_for_status()
        body = response.json()
        self.token = body["access_token"]
        self.id = body["player"]["id"]
        self.display_name = display_name

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self.client.get(path, headers=self.headers, **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self.client.post(path, headers=self.headers, **kwargs)

    def delete(self, path: str, **kwargs) -> httpx.Response:
        return self.client.delete(path, headers=self.headers, **kwargs)


def play_round(duel_id: int, picker: Player, responder: Player) -> bool:
    """Picks a category and has both players answer all three questions."""
    recommendations = picker.get(f"/duels/{duel_id}/recommendations")
    if recommendations.status_code != 200 or not recommendations.json():
        print(f"    no recommendations: {recommendations.status_code} {recommendations.text}")
        return False

    category = recommendations.json()[0]["category"]
    pick = picker.post(f"/duels/{duel_id}/rounds", json={"category": category})
    if pick.status_code != 201:
        print(f"    pick failed: {pick.status_code} {pick.text}")
        return False
    round_id = pick.json()["round_id"]

    for actor in (picker, responder):
        for position in range(1, QUESTIONS_PER_ROUND + 1):
            question = actor.get(f"/duels/{duel_id}/rounds/{round_id}/questions/{position}")
            if question.status_code != 200:
                print(f"    question fetch failed: {question.status_code} {question.text}")
                return False
            answer = actor.post(
                f"/duels/{duel_id}/rounds/{round_id}/questions/{position}/answer",
                json={"selected_choice_index": 0},
            )
            if answer.status_code != 200:
                print(f"    answer failed: {answer.status_code} {answer.text}")
                return False
    return True


def main() -> int:
    print(f"Smoke testing {BASE_URL}\n")
    client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)

    print("Health")
    health = client.get("/health")
    check("health endpoint responds", health.status_code == 200, health.text)
    if health.status_code != 200:
        print("\nServer unreachable — is it running?")
        return 1

    print("\nAuthentication")
    anna = Player(client, "Smoke Anna")
    bernd = Player(client, "Smoke Bernd")
    check("two accounts registered", anna.id != bernd.id)

    login = client.post("/auth/login", json={"email": anna.email, "password": PASSWORD})
    check("login returns a token", login.status_code == 200 and "access_token" in login.json())

    bad_login = client.post("/auth/login", json={"email": anna.email, "password": "wrong"})
    check("wrong password is rejected", bad_login.status_code == 401)

    unauthenticated = client.get("/duels")
    check("unauthenticated request is rejected", unauthenticated.status_code == 401)

    print("\nOpponent discovery")
    search = anna.get("/players/search", params={"q": "Smoke Bernd"})
    check(
        "search finds the other player",
        search.status_code == 200 and any(p["id"] == bernd.id for p in search.json()),
        search.text,
    )

    print("\nDuel")
    created = anna.post("/duels", json={"opponent_email": bernd.email})
    check("duel created by email", created.status_code == 201, created.text)
    if created.status_code != 201:
        return 1
    duel_id = created.json()["id"]

    started = time.monotonic()
    picker, responder = anna, bernd
    for sequence in range(1, TOTAL_ROUNDS + 1):
        ok = play_round(duel_id, picker, responder)
        check(f"round {sequence} played", ok)
        if not ok:
            break
        picker, responder = responder, picker

    state = anna.get(f"/duels/{duel_id}/state").json()
    check("duel reached the finished state", state.get("action") == "finished", str(state))
    # Real questions have real answer keys, so always picking choice 0 scores
    # somewhere between 0 and 24 — the point is that scoring ran at all.
    check(
        "scores are in range for 24 answered questions",
        all(0 <= state.get(key, -1) <= 24 for key in ("challenger_score", "opponent_score")),
        str(state),
    )
    print(
        f"    (full duel took {time.monotonic() - started:.1f}s, "
        f"{state.get('challenger_score')}:{state.get('opponent_score')})"
    )

    history = anna.get(f"/duels/{duel_id}/history")
    check("history is available", history.status_code == 200, history.text)
    check(
        "history contains all eight rounds",
        history.status_code == 200 and len(history.json()["rounds"]) == TOTAL_ROUNDS,
    )

    print("\nResearch")
    research_status = anna.get("/research/consent")
    check("research status readable", research_status.status_code == 200, research_status.text)
    research_enabled = research_status.json().get("research_enabled", True)

    if not research_enabled:
        # Expected for the beta: the programme is switched off until the
        # consent texts are approved. Consent must be refused, not recorded.
        print("    (research programme disabled on this server)")
        refused = anna.post("/research/consent", json={"general_consent": True})
        check("consent is refused while research is off", refused.status_code == 503)
    else:
        consent = anna.post("/research/consent", json={"general_consent": True})
        check("consent recorded", consent.status_code == 201, consent.text)

        questionnaire = anna.get("/research/questionnaire/current")
        check(
            "questionnaire endpoint responds",
            questionnaire.status_code == 200,
            questionnaire.text,
        )
        withdraw = anna.delete("/research/consent")
        check("consent can be withdrawn", withdraw.status_code == 204, withdraw.text)

    print("\nBilling")
    status = anna.get("/billing/status")
    check("billing status readable", status.status_code == 200, status.text)
    provider = status.json().get("provider") if status.status_code == 200 else None
    print(f"    provider: {provider}")

    if provider == "fake":
        checkout = anna.post("/billing/checkout")
        check("fake checkout activates the subscription", checkout.status_code == 200, checkout.text)
        after = anna.get("/billing/status").json()
        check("subscription reads back as active", after.get("active") is True, str(after))
        cancelled = anna.post("/billing/cancel")
        check("subscription can be cancelled", cancelled.status_code == 200, cancelled.text)
    elif provider == "none":
        blocked = anna.post("/billing/checkout")
        check("checkout is refused while billing is off", blocked.status_code == 503)
    else:
        print("    (stripe configured — skipping checkout, it needs a browser)")

    print("\nCleanup")
    for player in (anna, bernd):
        deleted = player.delete("/auth/me")
        check(f"{player.display_name} deleted", deleted.status_code == 204, deleted.text)
    locked_out = client.post("/auth/login", json={"email": anna.email, "password": PASSWORD})
    check("deleted account can no longer log in", locked_out.status_code == 401)

    print(f"\n{passed} passed, {len(failed)} failed")
    for failure in failed:
        print(f"  FAILED: {failure}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
