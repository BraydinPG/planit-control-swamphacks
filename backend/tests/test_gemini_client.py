import httpx
import pytest
from pydantic import BaseModel

from app.config import Settings
from app.gemini import GeminiClient, Image, Unavailable


class Answer(BaseModel):
    radius_miles: float


def client(transport, api_key: str | None = "test-key", model: str | None = "test-model"):
    return GeminiClient(api_key, model, timeout_seconds=1, transport=transport)


def never_called(prompt: str, schema: type[BaseModel]) -> str:
    raise AssertionError("transport must not be called")


def raises(exc: Exception):
    def transport(prompt: str, schema: type[BaseModel]) -> str:
        raise exc

    return transport


@pytest.mark.parametrize(("api_key", "model"), [(None, "m"), ("k", None), ("", "m")])
def test_missing_config_is_unavailable_without_network(api_key, model) -> None:
    result = client(never_called, api_key, model).generate_structured("p", Answer)
    assert not result.ok
    assert result.unavailable is Unavailable.MISSING_CONFIG


def test_valid_output_is_validated() -> None:
    result = client(lambda p, s: '{"radius_miles": 5}').generate_structured("p", Answer)
    assert result.ok
    assert result.value == Answer(radius_miles=5)


@pytest.mark.parametrize("raw", ["not json", '{"radius": 5}', ""])
def test_invalid_output_is_unavailable(raw: str) -> None:
    result = client(lambda p, s: raw).generate_structured("p", Answer)
    assert result.unavailable is Unavailable.INVALID_OUTPUT


@pytest.mark.parametrize("exc", [TimeoutError(), httpx.ReadTimeout("slow")])
def test_timeout_is_unavailable(exc: Exception) -> None:
    result = client(raises(exc)).generate_structured("p", Answer)
    assert result.unavailable is Unavailable.TIMEOUT


def test_other_errors_are_unavailable() -> None:
    result = client(raises(RuntimeError("boom"))).generate_structured("p", Answer)
    assert result.unavailable is Unavailable.ERROR


def test_settings_keep_key_secret() -> None:
    settings = Settings(gemini_api_key="super-secret", gemini_model="m", _env_file=None)
    assert "super-secret" not in repr(settings)
    assert GeminiClient.from_settings(settings).configured


def test_settings_default_to_unconfigured(monkeypatch) -> None:
    for name in ("GEMINI_API_KEY", "GEMINI_MODEL"):
        monkeypatch.delenv(name, raising=False)
    assert not GeminiClient.from_settings(Settings(_env_file=None)).configured


def test_images_reach_the_transport() -> None:
    seen = []

    def transport(prompt: str, schema: type[BaseModel], images) -> str:
        seen.extend(images)
        return '{"radius_miles": 1}'

    photo = Image(b"\xff\xd8\xff", "image/jpeg")
    assert client(transport).generate_structured("p", Answer, [photo]).ok
    assert seen == [photo]


def test_with_timeout_only_shortens() -> None:
    base = GeminiClient("k", "m", timeout_seconds=20)
    assert base.with_timeout(8)._timeout_seconds == 8
    assert base.with_timeout(60)._timeout_seconds == 20
    assert base.with_timeout(8).configured
