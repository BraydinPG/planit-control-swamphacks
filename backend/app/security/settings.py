"""Auth0 settings read from environment variables or backend/.env (auth/SETUP.md)."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.security.roles import DEFAULT_ROLES_CLAIM


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    auth0_domain: str | None = None
    auth0_audience: str | None = None
    auth0_roles_claim: str = DEFAULT_ROLES_CLAIM
    # Local-only development bypass. Never enable in a deployed environment.
    dev_auth_bypass: bool = False

    @field_validator("auth0_domain", "auth0_audience", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("auth0_domain")
    @classmethod
    def _bare_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.removeprefix("https://").removeprefix("http://").rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.auth0_domain and self.auth0_audience)

    @property
    def issuer(self) -> str:
        return f"https://{self.auth0_domain}/"

    @property
    def jwks_url(self) -> str:
        return f"https://{self.auth0_domain}/.well-known/jwks.json"


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()
