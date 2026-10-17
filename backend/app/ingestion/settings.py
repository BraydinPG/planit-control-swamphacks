"""Ingestion settings read from environment variables or backend/.env."""

from datetime import timedelta
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    nws_user_agent: str | None = None
    nws_base_url: str = "https://api.weather.gov"
    nws_timeout_seconds: float = 10.0
    nws_forecast_hours: int = 12
    feed_stale_after_minutes: int = 60
    feed_unavailable_after_minutes: int = 360

    @property
    def stale_after(self) -> timedelta:
        return timedelta(minutes=self.feed_stale_after_minutes)

    @property
    def unavailable_after(self) -> timedelta:
        return timedelta(minutes=self.feed_unavailable_after_minutes)


@lru_cache
def get_ingestion_settings() -> IngestionSettings:
    return IngestionSettings()
