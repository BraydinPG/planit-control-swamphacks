"""Backend settings read from environment variables or backend/.env.

See backend/.env.example for every variable. Only settings Rudra's modules consume are
declared here; Braydin's security, db, and ingestion modules read their own.
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: SecretStr | None = None
    gemini_model: str | None = None
    gemini_timeout_seconds: float = 10.0
    # Gemini 3 models think before answering; "low" keeps calls to a few seconds.
    # Leave empty for models without thinking levels.
    gemini_thinking_level: str | None = "low"


@lru_cache
def get_settings() -> Settings:
    return Settings()
