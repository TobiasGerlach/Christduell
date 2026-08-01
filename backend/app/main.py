from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth,
    billing,
    duels,
    health,
    notifications,
    players,
    questions,
    research,
)
from app.core.config import Settings, get_settings
from app.db.session import init_db

DEFAULT_SECRET_KEY = "dev-only-insecure-secret-change-me"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def _check_production_config(settings: Settings) -> None:
    """Refuses to start a non-local deployment with dev defaults.

    Booting with the shipped secret key would let anyone mint a valid token for
    any account, so this is a hard failure rather than a warning.
    """
    if settings.environment == "local":
        return

    problems: list[str] = []
    if settings.secret_key == DEFAULT_SECRET_KEY:
        problems.append("SECRET_KEY is still the development default")
    if settings.billing_provider == "fake":
        problems.append("BILLING_PROVIDER=fake would hand out free subscriptions")
    if problems:
        raise RuntimeError(
            f"Refusing to start in environment '{settings.environment}': " + "; ".join(problems)
        )


def create_app() -> FastAPI:
    settings = get_settings()
    _check_production_config(settings)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    # The Expo web build runs on a different origin than the API, so the browser
    # blocks its fetches without CORS. Locally any origin is fine; deployed, only
    # the origins listed in CORS_ORIGINS are allowed.
    allowed_origins = ["*"] if settings.environment == "local" else settings.cors_origins
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(billing.router)
    app.include_router(duels.router)
    app.include_router(notifications.router)
    app.include_router(players.router)
    app.include_router(questions.router)
    app.include_router(research.router)

    return app


app = create_app()
