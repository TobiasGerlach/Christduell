# Christduell — one place for every command you need locally.
# Run `make` (or `make help`) for the list.

.DEFAULT_GOAL := help
.PHONY: help setup backend backend-slow frontend web web-export seed migrate migration reset-db \
        test test-backend test-postgres test-frontend lint fmt check smoke maintenance clean \
        review apply-review demo-duels play reports reset-password

BACKEND := backend
FRONTEND := frontend
BASE_URL ?= http://localhost:8000

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- Setup ------------------------------------------------------------------

setup: ## Install backend and frontend dependencies
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && npm install

# --- Running ----------------------------------------------------------------

backend: ## Run the API at http://localhost:8000 (docs at /docs)
	cd $(BACKEND) && uv run fastapi dev app/main.py

frontend: ## Start Expo (scan the QR code with Expo Go)
	cd $(FRONTEND) && npx expo start

web: ## Start the Expo web build at http://localhost:8081
	cd $(FRONTEND) && npx expo start --web

web-export: ## Build the production web app; `make backend` then serves it at :8000
	cd $(FRONTEND) && npx expo export --platform web --output-dir ../$(BACKEND)/webbuild

# --- Database ---------------------------------------------------------------

migrate: ## Apply database migrations
	cd $(BACKEND) && uv run alembic upgrade head

migration: ## Generate a migration from model changes: make migration m="add x"
	@test -n "$(m)" || (echo 'Usage: make migration m="what changed"'; exit 1)
	cd $(BACKEND) && uv run alembic revision --autogenerate -m "$(m)"

seed: ## Migrate, then load demo players and questions
	cd $(BACKEND) && uv run python -m app.db.seed

reset-db: ## Delete the local database and rebuild it from scratch
	rm -f $(BACKEND)/christduell.db $(BACKEND)/christduell.db-wal $(BACKEND)/christduell.db-shm
	$(MAKE) seed

reset-password: ## Set a player's password by hand: make reset-password email=anna@example.com
	@test -n "$(email)" || (echo 'Usage: make reset-password email=<address> [pw=<password>]'; exit 1)
	cd $(BACKEND) && uv run python -m app.jobs.reset_password "$(email)" $(if $(pw),--password "$(pw)",)

reports: ## Triage questions players reported: make reports [a="fix 42" | a="keep 42"]
	cd $(BACKEND) && uv run python -m app.jobs.question_reports $(a)

maintenance: ## Run the housekeeping job (downgrade expired subscriptions)
	cd $(BACKEND) && uv run python -m app.jobs.maintenance

# --- Reviewing the questions ------------------------------------------------

review: ## Build and open the offline proofreading page for all questions
	uv run --project $(BACKEND) python scripts/build_review.py

apply-review: ## Apply a review export: make apply-review f=~/Downloads/question-review.json
	@test -n "$(f)" || (echo 'Usage: make apply-review f=~/Downloads/question-review.json [dry=1]'; exit 1)
	uv run --project $(BACKEND) python scripts/apply_review.py "$(f)" $(if $(dry),--dry-run,)

# --- Playing it locally -----------------------------------------------------

demo-duels: ## Create duels in every state between the demo players (needs a running API)
	BASE_URL=$(BASE_URL) uv run --project $(BACKEND) python scripts/seed_demo_duels.py

play: ## Print how to play both sides locally
	@echo "Terminal 1:  make reset-db && make backend-slow"
	@echo "Terminal 2:  make demo-duels   (duels in every state, so you can jump to any screen)"
	@echo "Terminal 3:  make web"
	@echo ""
	@echo "Then open these two URLs — each tab signs itself in and stays its own player:"
	@echo "  http://localhost:8081/?player=anna"
	@echo "  http://localhost:8081/?player=tobias"
	@echo ""
	@echo "The badge at the bottom right switches sides in one click. Logins are"
	@echo "anna@example.com / tobias@example.com, password christduell-dev."

backend-slow: ## Run the API with a 10-minute question timer (for unhurried UI testing)
	cd $(BACKEND) && QUESTION_TIME_LIMIT_SECONDS=600 uv run fastapi dev app/main.py

# --- Tests ------------------------------------------------------------------

test: test-backend test-frontend ## Run all tests

test-backend: ## Run the backend test suite
	cd $(BACKEND) && uv run pytest -q

test-postgres: ## Run the backend suite against a throwaway PostgreSQL
	./scripts/test-postgres.sh

test-frontend: ## Typecheck and unit-test the app
	cd $(FRONTEND) && npx tsc --noEmit
	cd $(FRONTEND) && npm test --silent

lint: ## Lint the backend
	cd $(BACKEND) && uv run ruff check .

fmt: ## Auto-fix what the linter can fix
	cd $(BACKEND) && uv run ruff check --fix .

check: lint test ## Everything CI runs
	cd $(BACKEND) && uv run alembic check

smoke: ## End-to-end check against a running server (BASE_URL=... to target another)
	cd $(BACKEND) && BASE_URL=$(BASE_URL) uv run python ../scripts/smoke_test.py

clean: ## Remove caches
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache
