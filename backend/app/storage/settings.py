"""Photo storage settings, read from environment variables or backend/.env."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    vultr_object_storage_endpoint: str | None = None
    vultr_object_storage_access_key: SecretStr | None = None
    vultr_object_storage_secret_key: SecretStr | None = None
    vultr_object_storage_bucket: str | None = None
    photo_local_dir: str = "./.photos"
    photo_max_bytes: int = 5 * 1024 * 1024
    photo_url_seconds: int = 900

    @property
    def vultr_configured(self) -> bool:
        return all(
            (
                self.vultr_object_storage_endpoint,
                self.vultr_object_storage_access_key,
                self.vultr_object_storage_secret_key,
                self.vultr_object_storage_bucket,
            )
        )


@lru_cache
def get_storage_settings() -> StorageSettings:
    return StorageSettings()
