# Christduell — launch checklist

Everything between here and paying users. Ordered by what blocks what.

**Status legend:** `[x]` done in the codebase · `[ ]` still open · **(you)** = only you can do
it (accounts, money, legal, content).

---

## 0. Read this first — the honest timeline

Auth, invites, push, payments, migrations and the matching UI now exist and are tested. What
is left splits into two piles:

- **Engineering** — roughly 1–2 focused days (password reset, deploy). The question bank is
  written; it needs review, not authoring.
- **Calendar time you cannot compress** — Apple/Google developer account approval, Stripe
  account verification, app review, and a data-protection opinion on the research consent.
  Each of these is days-to-weeks of *waiting*, and they only start once you file them.

A realistic one-week launch is therefore **web-first and free-only**:

| | Web-first (recommended) | Native + paid |
|---|---|---|
| Blocked by app review | no | yes (days, often a rejection round) |
| Blocked by IAP setup | no (Stripe on web is allowed) | yes (tax/banking forms first) |
| Push notifications | no (web push isn't wired) | yes |
| Realistic in 7 days | yes | no |

Recommendation: ship the Expo **web** build to a domain this week with `BILLING_PROVIDER=none`,
run the closed beta, and file the store + Stripe paperwork **today** in parallel so the native
paid release follows a few weeks later.

Whichever you choose, §1 and §2 are mandatory.

---

## 1. Blockers — cannot launch without these

### 1.1 Password reset **(you + ~half a day of work)**

- [ ] **There is no "forgot password" flow.** Registration, login, password *change* and
      account deletion all work, but a user who forgets their password is permanently locked
      out and will just leave. This needs an email sender (Resend, Postmark, Brevo, Azure
      Communication Services), a signed one-time reset token, and two screens.
- [ ] Decide the email provider **(you)** — everything else waits on that account.
- [ ] While you are there: no email *verification* either, so anyone can register with someone
      else's address. Acceptable for a beta, not for charging money.

### 1.2 Question content — **fact-check still open (you)**

- [x] The bank went from 65 to **651 questions, ~50 per category**, in
      `backend/app/db/fixtures/questions/<category>.json` (one file per category). Ecumenical
      framing, difficulty seeded at 850 / 1000 / 1150, and every question carries a one-line
      explanation; 283 also carry a Bible reference.
- [x] **Players report bad questions instead of you proofreading all 651.** Every revealed
      answer has a "Frage melden" link. Once `QUESTION_REPORT_RETIRE_THRESHOLD` distinct players
      (default 3) call a question wrong or ambiguous, it retires itself and stops being dealt —
      no action needed from you at 3am. `make reports` shows what came in, `make reports
      a="fix 42"` / `a="keep 42"` closes it out.
- [ ] **Optional but cheap: spot-check the ~100 riskiest questions (you, ~40 minutes).**
      Reporting only helps *after* someone hits a wrong answer, and in a quiz about a text people
      know well that is the kind of error they screenshot rather than report. `make review`, then
      filter to `facts_numbers_dates` and `history` — dates and counts are where a language model
      is most likely to be confidently wrong. The rest can safely wait for reports.
- [ ] Decide whether the confessional balance is right for your audience. Where traditions
      differ, questions name the tradition ("Was feiert die katholische Kirche an Fronleichnam?")
      rather than picking a side.
- [ ] `make check` now validates the bank: four distinct choices, a valid answer index, no
      duplicate prompts, and an even spread of the correct answer across all four positions
      (the first draft had 88 % of answers in position A — the fixtures are deliberately
      shuffled, and a test keeps them that way).
- [ ] Note: `select_questions_for_round` picks by rating proximity but has **no memory of what
      a player has already seen**. At ~50 per category that is tolerable; if repeats bother you,
      add a "not answered by this player" filter
      (`backend/app/services/question_selection.py:20`).
- [ ] Seeding adds and updates but never **deletes**: a question removed from the fixtures stays
      in an already-seeded database. Use `make reset-db` locally; in production, delete the row
      by hand.

### 1.3 Legal pages **(you — required before taking money in Germany)**

- [ ] **Impressum** (§5 DDG)
- [ ] **Datenschutzerklärung** — must cover: account data, duel data, push tokens, the research
      questionnaires (incl. Art. 9 health data), Stripe as processor, Azure as host, retention
      periods, and the rights under Art. 15–21 GDPR.
- [ ] **AGB** — subscription terms, auto-renewal, cancellation.
- [ ] **Widerrufsbelehrung** + the "Jetzt kaufen"-style button labelling for consumer
      subscriptions.
- [ ] Host them at stable URLs and link them from the app (the login screen and the
      subscription screen already reserve space for the links — wire them up).
- [ ] Store listings and Stripe both require a public privacy-policy URL, so this blocks them
      too.

### 1.4 Research consent needs a legal opinion **(you)**

- [ ] The free tier's price is questionnaire participation, including **ADHD (ASRS) and autism
      (AQ) screeners** — Art. 9 special-category health data. "Give us your health data or pay
      €5" is exactly the pattern where GDPR's *freely given* consent gets challenged. Get a
      written opinion from a German data-protection lawyer or your institution's DPO **before**
      the first real participant.
- [ ] If a university is involved: ethics-board approval.
- [ ] Confirm licensing to redistribute **ASRS v1.1** and the **AQ** in an app.
- [ ] The AQ fixture has **34 items; the AQ is a 50-item instrument**
      (`backend/app/db/fixtures/questionnaire_autism_screener.json`). Either complete it or
      rename it so you are not implying you administered the AQ-50.
- [ ] Decide a retention period and who may access the research data.

*Implemented already:* consent is opt-in, health-data consent is a separate opt-in,
questionnaires only appear after 5 finished duels, withdrawal severs the identity link, and
deleting the account withdraws consent automatically.

### 1.5 Deploy the backend **(you, ~half a day)**

- [ ] `cd infra && terraform apply` — now provisions HTTPS-only, always-on, a health check,
      a generated `SECRET_KEY`, and passes billing/push settings through.
- [ ] Set `cors_origins` to the web build's real origin, or the browser blocks every request.
- [ ] Set the GitHub repo secrets (`ACR_LOGIN_SERVER`, `ACR_USERNAME`, `ACR_PASSWORD`,
      `AZURE_CREDENTIALS`, `AZURE_WEBAPP_NAME`) and run **Backend Deploy** once by hand — the
      deploy workflow has never run.
- [ ] **If a database already exists in Azure** (created by the old `create_all` path), do not
      let it meet the migrations cold:
      ```sh
      # once, against the existing DB — it already matches revision 0001
      alembic stamp 0001 && alembic upgrade head
      ```
      A fresh deployment needs nothing: startup runs `alembic upgrade head` itself.
- [ ] Take a backup **before** the first migration: `./scripts/backup-db.sh`.
- [ ] Verify the deployment end to end:
      `BASE_URL=https://<app>.azurewebsites.net make smoke` (creates two throwaway accounts,
      plays a full duel, deletes them again).
- [ ] Custom domain + certificate **(you)** — `*.azurewebsites.net` is fine for a beta, not for
      a launch.
- [ ] Schedule `scripts/backup-db.sh` (cron/GitHub Action). The SQLite file on App Service
      Files has no managed backup behind it.
- [ ] Schedule `make maintenance` daily — it downgrades lapsed subscriptions.

---

## 2. Blockers if you want to charge money

### 2.1 Choose the payment rail **(you — decide first, it changes the work)**

- [ ] **Web (Stripe)** — implemented and tested. Allowed because a browser is not an app store.
- [ ] **iOS/Android in-app purchase** — Apple and Google *require* IAP for digital
      subscriptions inside their apps (15–30 %). Stripe-in-the-app gets the build rejected.
      `app/services/billing.py` is provider-shaped so this lands as a fourth provider
      (RevenueCat is the usual shortcut), but it is a separate integration, not a config flag.

### 2.2 Stripe setup **(you)**

- [ ] Create the Stripe account and complete identity/bank verification (this takes days).
- [ ] Create the €5/month recurring **Price**, note the `price_...` id.
- [ ] Enable **Stripe Tax** — the checkout session already requests `automatic_tax`, but the
      tax registrations have to be configured in the dashboard, and EU VAT (OSS) is on you.
- [ ] Add the webhook endpoint `POST https://<your-api>/billing/webhook/stripe` subscribed to
      `checkout.session.completed`, `customer.subscription.created`,
      `customer.subscription.updated`, `customer.subscription.deleted`; copy the `whsec_...`.
- [ ] Set `billing_provider = "stripe"` plus `stripe_secret_key`, `stripe_price_id`,
      `stripe_webhook_secret`, `billing_success_url`, `billing_cancel_url` in
      `infra/terraform.tfvars`, then apply.
- [ ] Test with a real card in test mode, then **one real €5 charge**, then refund it. Confirm
      the tier flips to `paid` and the questionnaire prompt disappears.
- [ ] Verify a cancellation: access must run to the end of the paid period, then drop back to
      the research tier (`make maintenance`).

*Implemented already:* checkout, cancel-at-period-end, webhook with mandatory signature
verification, entitlement expiry, and the "paid tier owes no questionnaires" rule — all covered
by tests. `BILLING_PROVIDER=fake` lets you exercise the whole flow locally without Stripe;
Terraform rejects it and the app refuses to boot with it outside local.

---

## 3. Mobile release (skip for a web-first launch)

- [ ] Apple Developer Program membership, 99 $/yr, plus the paid-apps agreement with tax and
      banking details **(you — days of processing)**.
- [ ] Google Play Developer account, 25 $ one-off, plus identity verification.
- [ ] `eas.json` + `eas build` — there is no EAS config yet, and `app.json` has no EAS project
      id, which push notifications need.
- [ ] Push credentials: `eas credentials` (APNs key for iOS, FCM for Android). Then set
      `push_enabled = true` in tfvars.
- [ ] Test a real push on a **physical** device — simulators cannot receive them.
- [ ] Store listing: screenshots (6.7" and 5.5" for iOS), description, keywords, support URL,
      privacy-policy URL.
- [ ] Apple **App Privacy** labels and Google **Data safety** form — declare the health-data
      questionnaires honestly; a mismatch here gets apps pulled.
- [ ] Age rating questionnaire.
- [ ] Apple requires in-app **account deletion** for any app with sign-up — implemented
      (`DELETE /auth/me`, "Konto löschen" in the profile screen). Point the reviewer at it in
      the review notes.
- [ ] Budget for at least one rejection round.

---

## 4. Before real users touch it (hardening)

- [ ] **Rate-limit `/auth/login` and `/auth/register`.** Nothing currently slows down a
      password-guessing loop. `slowapi` or an App Service / front-door rule. Related: login
      skips the password hash entirely for an unknown address, so response time still leaks
      whether an account exists. Cheap fix once you touch this file: verify against a dummy
      hash in the not-found branch.
- [ ] **`GET /duels` runs a handful of queries per duel** (two display names, two score
      aggregates). Fine at a few dozen duels per player, worth batching before it is thousands.
- [ ] **The container runs as root.** Deliberate for now — App Service mounts `/home` as root,
      and a non-root user would need the mount permissions sorted out first. Revisit with the
      Postgres move, not before launch.
- [ ] **The Notification Hub in Terraform is unused** — push goes through Expo. Free tier, so
      it costs nothing, but delete it if you settle on Expo for good.
- [ ] Sentry (or equivalent) in both backend and app — right now a crash in production is
      invisible.
- [ ] Application Insights or at least an uptime check against `/health`.
- [ ] Decide token lifetime: access tokens currently last 30 days and cannot be revoked
      individually. Fine for a beta; add refresh tokens + revocation before scale.
- [ ] Expo push receipts: `DeviceNotRegistered` tokens are logged but never cleared from
      `player.push_token` (`backend/app/services/push.py:96`).
- [ ] Load-sanity: SQLite on Azure Files is **single-writer**. Do not scale the App Service
      past one instance without moving to Postgres — `AUTO_MIGRATE` on multiple booting
      instances would also race.
- [ ] Legal/consent copy in `ResearchConsentScreen.tsx` is a plain-language summary written by
      an engineer. Replace with the text your lawyer approves, and bump `consent_version`
      (`backend/app/models/domain.py`) whenever it changes.

---

## 5. Nice to have (post-launch)

- [ ] Duel timeouts — a player who abandons a duel blocks it forever; no expiry job exists.
- [ ] Leaderboard / friends list.
- [ ] Question reporting ("this answer is wrong") — you will want this the moment strangers
      play.
- [ ] Category display names live in `duels.py`; move them into the app if you ever add a
      second language.
- [ ] Component tests for the React Native screens. `@testing-library/react-native` currently
      conflicts with the pinned React version (needs `react-test-renderer` ≥ 19.2.8 against
      React 19.2.3), so only the API-client logic is unit-tested. Revisit after an Expo SDK
      bump.
- [ ] Replace the 8-second polling in `DuelScreen.tsx` with a push-triggered refresh.

---

## 6. What was built (so you know what to test)

| Area | What exists now |
|---|---|
| Auth | Register / login / JWT bearer tokens, password change, GDPR account deletion (soft-delete that scrubs PII and withdraws research consent) |
| Authorisation | Every player-scoped endpoint reads identity from the token — `player_id` is no longer accepted from the client. `tests/test_auth_required.py` locks this in for all 26 endpoints |
| Invites | Player search (exact email or display-name prefix), challenge by id or email, random matchmaking by rating, decline a challenge |
| Push | Real Expo push delivery off the request path; challenge / your-turn / duel-finished events |
| Billing | Provider abstraction (`none` / `fake` / `stripe`), checkout, cancel-at-period-end, signed webhooks, entitlement expiry + downgrade job |
| Migrations | Alembic, revisions `0001` (pre-existing schema) and `0002` (accounts, billing, research); `alembic check` runs in CI |
| App | Login/register, opponent search + challenge + random duel, subscription screen, profile (rename, logout, delete), research consent, questionnaire renderer for all 7 question types |
| Content | 651 questions across 13 categories, each with an explanation and (where applicable) a Bible reference, revealed with the answer |
| Infra | HTTPS-only, always-on, health check, TLS 1.2, generated signing key, all new settings wired |
| CI | Runs on push and PR: backend lint + tests + migration drift, frontend typecheck + tests, `terraform fmt`/`validate` |

### Verify it locally

```sh
make setup          # install backend + frontend dependencies
make reset-db       # migrate and seed (demo logins printed at the end)
make backend        # API on :8000, docs at /docs
make web            # Expo web on :8081  (or `make frontend` for the phone)
make check          # lint + backend tests + frontend tests + migration drift
make smoke          # end-to-end against the running server (needs `make backend`)
```

Demo logins after `make reset-db`: `anna@example.com` / `tobias@example.com`,
password `christduell-dev`.

To exercise the paid tier locally, start the API with `BILLING_PROVIDER=fake` — "subscribe"
then grants 30 days instantly, with no Stripe account involved:

```sh
cd backend && BILLING_PROVIDER=fake uv run fastapi dev app/main.py
```

To see what push *would* send without sending it, leave `PUSH_ENABLED=false` and watch the
backend log.
