from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Christduell API"
    environment: str = "local"
    database_url: str = "sqlite:///./christduell.db"
    # Run `alembic upgrade head` on startup. On Postgres this is guarded by an
    # advisory lock, so overlapping instances queue rather than race.
    auto_migrate: bool = True
    # Connection pool, Postgres only. The default App Service plan is small and
    # Postgres burstable tiers cap connections, so stay modest.
    db_pool_size: int = 5
    db_max_overflow: int = 5

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

    # Days without any move before an open duel is closed by the maintenance
    # job. Pending challenges quietly disappear; active duels end at the
    # current score.
    duel_inactivity_expiry_days: int = 3

    # Login/register rate limits (in-memory, correct for one instance).
    # Login is limited per account so a shared church wifi cannot lock everyone
    # out; register is limited per IP to slow down mass account creation.
    login_rate_limit_attempts: int = 10
    login_rate_limit_window_seconds: int = 300
    register_rate_limit_attempts: int = 20
    register_rate_limit_window_seconds: int = 600

    # How many distinct players must report a question before it retires itself.
    # Low on purpose: a wrong answer key in a Bible quiz costs more trust than
    # briefly losing one question out of several hundred.
    question_report_retire_threshold: int = 3

    # --- CORS -------------------------------------------------------------
    # Comma-separated list of allowed browser origins. Only needed if the web
    # build is hosted somewhere other than this API — the container serves the
    # Expo web export itself (see web_build_dir), and same-origin requests
    # never involve CORS.
    # NoDecode: the env source must not JSON-decode this; _split_origins parses
    # the raw comma-separated string (an empty string means no extra origins).
    cors_origins: Annotated[list[str], NoDecode] = []

    # --- Web build --------------------------------------------------------
    # Directory containing the Expo web export (`npx expo export --platform
    # web`). If it exists, the API serves it at "/"; if not (local dev, where
    # `make web` runs the Expo dev server instead), the API serves JSON only.
    web_build_dir: str = "webbuild"

    # --- Push notifications ----------------------------------------------
    push_enabled: bool = False
    # Web Push (browsers, incl. installed PWAs). Enabled by simply configuring
    # the VAPID key pair — separate from push_enabled, which gates Expo/native.
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:me@tobias-gerlach.de"

    @property
    def web_push_enabled(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key)
    expo_access_token: str | None = None
    expo_push_url: str = "https://exp.host/--/api/v2/push/send"
    azure_notification_hub_connection_string: str | None = None
    azure_notification_hub_name: str | None = None

    # --- Research ---------------------------------------------------------
    # Master switch for the research programme. True locally so development and
    # tests see the whole flow; the Terraform default is FALSE, because the
    # consent texts must be lawyer-approved before real participants see them.
    research_enabled: bool = True

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
