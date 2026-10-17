"""Server-side Gemini client.

Every call returns a `GeminiResult`: either a schema-validated value or an `Unavailable`
reason. It never raises to callers, so each endpoint can switch to its deterministic
fallback. The API key stays on the server and is never logged or returned.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# (prompt, schema) -> raw JSON text. Injectable so tests never touch the network.
Transport = Callable[[str, type[BaseModel]], str]


class Unavailable(StrEnum):
    MISSING_CONFIG = "missing_config"
    TIMEOUT = "timeout"
    ERROR = "error"
    INVALID_OUTPUT = "invalid_output"


@dataclass(frozen=True)
class GeminiResult(Generic[T]):
    value: T | None = None
    unavailable: Unavailable | None = None

    @property
    def ok(self) -> bool:
        return self.value is not None


class GeminiClient:
    def __init__(
        self,
        api_key: str | None,
        model: str | None,
        timeout_seconds: float,
        transport: Transport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def from_settings(cls, settings: Settings) -> "GeminiClient":
        key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        return cls(key, settings.gemini_model, settings.gemini_timeout_seconds)

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._model)

    def generate_structured(self, prompt: str, schema: type[T]) -> GeminiResult[T]:
        """Ask Gemini for JSON matching `schema` and validate it before returning."""
        if not self.configured:
            return GeminiResult(unavailable=Unavailable.MISSING_CONFIG)
        try:
            raw = (self._transport or self._call_gemini)(prompt, schema)
        except Exception as exc:
            reason = Unavailable.TIMEOUT if _is_timeout(exc) else Unavailable.ERROR
            logger.warning("Gemini call failed: %s (%s)", reason, type(exc).__name__)
            return GeminiResult(unavailable=reason)
        try:
            return GeminiResult(value=schema.model_validate_json(raw))
        except ValidationError:
            logger.warning("Gemini output failed %s validation", schema.__name__)
            return GeminiResult(unavailable=Unavailable.INVALID_OUTPUT)

    def _call_gemini(self, prompt: str, schema: type[BaseModel]) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(timeout=int(self._timeout_seconds * 1000)),
        )
        response = client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=schema.model_json_schema(),
            ),
        )
        return response.text or ""


def _is_timeout(exc: BaseException) -> bool:
    import httpx

    return isinstance(exc, TimeoutError | httpx.TimeoutException)


def get_gemini_client() -> GeminiClient:
    """FastAPI dependency. Override in tests with `app.dependency_overrides`."""
    return GeminiClient.from_settings(get_settings())
