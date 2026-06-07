from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import duels, health, notifications
from app.core.config import get_settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.include_router(health.router)
    app.include_router(duels.router)
    app.include_router(notifications.router)

    return app


app = create_app()
