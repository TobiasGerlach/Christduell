from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Christduell API"
    environment: str = "local"
    database_url: str = "sqlite:///./christduell.db"

    # Push notifications (Expo push service / Azure Notification Hubs)
    expo_access_token: str | None = None
    azure_notification_hub_connection_string: str | None = None
    azure_notification_hub_name: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
