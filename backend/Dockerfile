# Build context is the REPO ROOT, not backend/ — the image also compiles the
# Expo web app and serves it from the API:
#
#     docker build -f backend/Dockerfile -t christduell-backend .

# --- Stage 1: compile the Expo web app --------------------------------------
FROM node:22-slim AS webbuild

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# No EXPO_PUBLIC_API_URL: a production web build defaults to same-origin
# relative URLs (see src/api/client.ts), because this image serves both.
RUN npx expo export --platform web && node scripts/inject-pwa.mjs dist

# --- Stage 2: the API image ---------------------------------------------------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first so they're cached independently of app code changes.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY backend/app ./app
# The app applies migrations on startup, so alembic.ini and the revisions have
# to be in the image — without them the container fails to boot.
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
# The web app, served by the API at "/" (WEB_BUILD_DIR in config.py).
COPY --from=webbuild /frontend/dist ./webbuild
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
