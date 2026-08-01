from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Christduell API"
    environment: str = "local"
    database_url: str = "sqlite:///./christduell.db"
    # Run `alembic upgrade head` on startup. Correct for a single-instance
    # deployment; turn it off if several instances ever boot concurrently and
    # run migrations as a separate deploy step instead.
    auto_migrate: bool = True

    # --- Auth -------------------------------------------------------------
    # MUST be overridden outside local dev — `create_app` refuses to boot with
    # the default value when environment != "local".
    secret_key: str = "dev-only-insecure-secret-change-me"
    # Mobile clients can't easily do a refresh-token dance, so access tokens are
    # long-lived; shorten this once refresh tokens exist.
    access_token_expire_minutes: int = 60 * 24 * 30

    # --- Gameplay ---------------------------------------------------------
    # Seconds a player has per question. Raise it locally when you want to look
    # at a screen instead of racing the clock; keep 30 in production.
    question_time_limit_seconds: float = 30.0

    # --- CORS -------------------------------------------------------------
    # Comma-separated list of allowed browser origins for the Expo web build.
    cors_origins: list[str] = []

    # --- Push notifications ----------------------------------------------
    push_enabled: bool = False
    expo_access_token: str | None = None
    expo_push_url: str = "https://exp.host/--/api/v2/push/send"
    azure_notification_hub_connection_string: str | None = None
    azure_notification_hub_name: str | None = None

    # --- Billing ----------------------------------------------------------
    # "none"   — subscriptions disabled, everyone stays on the research tier
    # "fake"   — local/testing provider, checkout activates instantly
    # "stripe" — real Stripe Checkout subscriptions (web only; the mobile stores
    #            require their own in-app purchase flow, see todos.md)
    billing_provider: str = "none"
    subscription_price_eur: str = "5.00"
    stripe_secret_key: str | None = None
    stripe_price_id: str | None = None
    stripe_webhook_secret: str | None = None
    billing_success_url: str = "http://localhost:8081/billing/success"
    billing_cancel_url: str = "http://localhost:8081/billing/cancel"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
