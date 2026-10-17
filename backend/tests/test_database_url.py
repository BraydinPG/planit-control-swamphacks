import pytest
from fastapi.testclient import TestClient

from app.db import DatabaseSettingsError, get_database_url, validate_database_url
from app.main import app

DOCUMENTED_URL = "postgresql://USER:PASSWORD@HOST:5432/tsdb?sslmode=require"


def test_documented_tiger_cloud_url_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DOCUMENTED_URL)
    assert get_database_url() == DOCUMENTED_URL


@pytest.mark.parametrize("sslmode", ["require", "verify-ca", "verify-full"])
def test_remote_host_accepts_strict_sslmodes(monkeypatch: pytest.MonkeyPatch, sslmode: str) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        f"postgresql://USER:PASSWORD@example.tigerdata.com:5432/tsdb?sslmode={sslmode}",
    )
    assert validate_database_url() is not None


def test_tiger_cloud_url_without_sslmode_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://USER:PASSWORD@example.tigerdata.com:5432/tsdb")
    with pytest.raises(DatabaseSettingsError, match="sslmode=require"):
        get_database_url()


def test_local_url_may_omit_sslmode(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql://planit:planit@localhost:5432/planit"
    monkeypatch.setenv("DATABASE_URL", url)
    assert get_database_url() == url


def test_missing_url_does_not_block_startup_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert validate_database_url() is None
    with pytest.raises(DatabaseSettingsError, match="DATABASE_URL is not set"):
        get_database_url()


def test_backend_starts_with_documented_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DOCUMENTED_URL)
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_backend_refuses_to_start_when_tiger_cloud_ssl_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://USER:PASSWORD@example.tigerdata.com:5432/tsdb")
    with pytest.raises(DatabaseSettingsError, match="sslmode=require"):
        with TestClient(app):
            pass
