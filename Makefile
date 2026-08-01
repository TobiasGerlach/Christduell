# Christduell — one place for every command you need locally.
# Run `make` (or `make help`) for the list.

.DEFAULT_GOAL := help
.PHONY: help setup backend frontend web seed migrate migration reset-db \
        test test-backend test-frontend lint fmt check smoke maintenance clean

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

maintenance: ## Run the housekeeping job (downgrade expired subscriptions)
	cd $(BACKEND) && uv run python -m app.jobs.maintenance

# --- Tests ------------------------------------------------------------------

test: test-backend test-frontend ## Run all tests

test-backend: ## Run the backend test suite
	cd $(BACKEND) && uv run pytest -q

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
