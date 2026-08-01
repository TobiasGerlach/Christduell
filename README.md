# Christduell

A Quizduell-style trivia duel app for playful Christian education — challenge friends, answer Bible and faith-themed questions, and climb the leaderboard.

## Project structure

- `backend/` — FastAPI backend (Python, managed with `uv`), deployed to Azure. Owns game logic, question banks, matchmaking, scoring, push notification dispatch, and the research/questionnaire module.
- `frontend/` — Expo / React Native (TypeScript) mobile app. Talks to the backend over REST and registers for push notifications.
- `infra/` — Terraform for the Azure deployment (ACR, App Service, persistent SQLite on Azure Files, Notification Hub). See `infra/README.md`.
- `scripts/` — operational helpers: `backup-db.sh` downloads the production SQLite database, `smoke_test.py` exercises a running deployment end to end.

## Features

- **Accounts** — email/password registration, JWT bearer tokens, password change, and GDPR
  account deletion that scrubs personal data while keeping past duels intact.
- **Duels** — Quizduell-style asynchronous 1v1 matches across 13 faith-themed categories, with Elo-style ratings for both players and questions from day one. Challenge someone by name or email, or get matched with a similarly-rated stranger.
- **Push notifications** — "you've been challenged", "you're up", "duel finished", delivered through the Expo push service.
- **Subscriptions** — €5/month removes the questionnaire obligation. Stripe Checkout on the web, behind a provider abstraction (`none` / `fake` / `stripe`) so the app-store in-app-purchase flow can slot in later.
- **Research programme** — free ("research" tier) players are periodically invited to complete questionnaires (faith background, then optional ADHD/autism screeners). Answers are stored only under a pseudonymous UUID, gated behind explicit consent (with a separate opt-in for health data) and a GDPR-style right to withdraw. A paid tier skips questionnaires. See `backend/app/services/research.py`.

See [`todos.md`](todos.md) for what is still missing before launch.

## Getting started

Everything runs through the `Makefile` — `make` on its own lists the targets.

```sh
make setup      # install backend and frontend dependencies
make reset-db   # apply migrations and seed demo players + questions
make backend    # API on http://localhost:8000 (docs at /docs)
make web        # Expo web build on http://localhost:8081
make frontend   # Expo dev server for a phone (Expo Go)
```

`make reset-db` prints the demo logins (password `christduell-dev`). Open two browser windows
against `make web` and log in as each to play both sides of a duel.

Configuration lives in `backend/.env` and `frontend/.env` — copy the `.env.example` next to
each. To try the paid tier without a Stripe account, start the API with `BILLING_PROVIDER=fake`;
checkout then grants 30 days instantly.

### Playing it locally

```sh
make play     # prints the three commands and the two URLs
```

Each browser tab keeps its own session, so `?player=anna` and `?player=tobias` can be two
ordinary tabs side by side rather than a normal window and a private one — the stored token is
namespaced per demo player. The badge at the bottom right switches sides in one click. This
only exists in a web development build.

`make backend-slow` runs the API with a ten-minute question timer so you can look at a screen
instead of racing a 30-second clock, and `make demo-duels` leaves a duel in every interesting
state (finished, your turn, opponent's turn, undecided challenge) so you don't have to play
eight rounds to reach the history screen.

### When players report a bad question

Every revealed answer has a "Frage melden" link. A question that enough distinct players call
wrong or ambiguous retires itself — it stops being dealt into new rounds while staying in the
database for review. Rounds already in progress are unaffected.

```sh
make reports              # what came in, most-reported first
make reports a="fix 42"   # you corrected it in the fixtures
make reports a="keep 42"  # it was fine; dismiss and put it back
```

### Proofreading the questions

```sh
make review                                          # builds and opens the review page
make apply-review f=~/Downloads/question-review.json # feeds your corrections back in
```

A single offline HTML file with all questions, one per screen. You pick the answer you think is
right before it reveals the stored one, so a wrong answer key announces itself instead of being
skimmed past. `Enter` accepts, `F` flags, `E` edits inline; progress lives in the browser, and
the export applies back to the fixtures.

### Tests

```sh
make check    # lint + backend tests + frontend typecheck/tests + migration drift
make smoke    # end-to-end HTTP run against a running server
```

`make smoke` registers two throwaway accounts, plays a complete eight-round duel, walks the
research and billing flows, then deletes the accounts. Point it at a deployment with
`BASE_URL=https://… make smoke`.

### Database migrations

Schema changes go through Alembic; the app runs `alembic upgrade head` on startup.

```sh
make migration m="add something"   # generate from model changes
make migrate                       # apply
```

## Stack

| Layer        | Choice                                   |
|--------------|------------------------------------------|
| Backend      | FastAPI + uv, deployed to Azure          |
| Database     | SQLite (WAL mode) on Azure Files; local SQLite in dev |
| Frontend     | Expo / React Native (TypeScript)         |
| Push         | Expo Notifications / Azure Notification Hubs |
| Infra        | Terraform (Azure)                        |
| Auth         | JWT (PyJWT) + Argon2 password hashing    |
| Payments     | Stripe Checkout subscriptions (web)      |
| Migrations   | Alembic                                  |
| CI/CD        | GitHub Actions (`.github/workflows/`)    |
