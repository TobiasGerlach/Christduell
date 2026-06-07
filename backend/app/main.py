from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import duels, health, notifications, players
from app.core.config import get_settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    if settings.environment == "local":
        # The Expo dev server (web/Metro) runs on a different origin than the
        # API, so the browser blocks fetches without permissive CORS here.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health.router)
    app.include_router(duels.router)
    app.include_router(notifications.router)
    app.include_router(players.router)

    return app


app = create_app()
