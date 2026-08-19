from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

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


class SpaStaticFiles(StaticFiles):
    """Serves the Expo web export, answering unknown extension-less paths with
    index.html so a reload inside the single-page app does not 404."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and "." not in path.rsplit("/", 1)[-1]:
                return await super().get_response("index.html", scope)
            raise


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

    if settings.billing_provider == "stripe":
        # Better to refuse the deploy than to show a subscribe button that 503s,
        # or to accept webhooks whose signature cannot be verified.
        for name, value in (
            ("STRIPE_SECRET_KEY", settings.stripe_secret_key),
            ("STRIPE_PRICE_ID", settings.stripe_price_id),
            ("STRIPE_WEBHOOK_SECRET", settings.stripe_webhook_secret),
            ("BILLING_SUCCESS_URL", settings.billing_success_url),
            ("BILLING_CANCEL_URL", settings.billing_cancel_url),
        ):
            if not value:
                problems.append(f"BILLING_PROVIDER=stripe but {name} is not set")

    if settings.push_enabled and not settings.cors_origins and settings.environment != "local":
        # Not fatal on its own, but a deployed API with no allowed origin cannot
        # serve the web build at all — worth failing early rather than debugging
        # CORS errors in a browser console.
        problems.append("CORS_ORIGINS is empty, so no browser origin may call this API")

    if problems:
        raise RuntimeError(
            f"Refusing to start in environment '{settings.environment}': " + "; ".join(problems)
        )


def create_app() -> FastAPI:
    settings = get_settings()
    _check_production_config(settings)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    # In production the API serves the web build itself (see the mount below),
    # so requests are same-origin and CORS never applies. CORS_ORIGINS only
    # matters if the web build is ever hosted elsewhere; locally the Expo dev
    # server on :8081 is a different origin, so any origin is allowed.
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

    # Mounted last so every API route above wins; anything else falls through
    # to the static files. Absent directory = API-only mode (local dev).
    web_build = Path(settings.web_build_dir)
    if web_build.is_dir():
        app.mount("/", SpaStaticFiles(directory=web_build, html=True), name="web")

    return app


app = create_app()
