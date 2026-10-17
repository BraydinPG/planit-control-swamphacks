"""Unit tests for diagnostic safety, never real Tiger Data acceptance."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
spec = importlib.util.spec_from_file_location(
    "integration_probe", ROOT / "frontend/scripts/probe-integration.py"
)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_missing_placeholder_and_local_databases_never_connect(monkeypatch):
    monkeypatch.setattr(
        sqlalchemy, "create_engine", lambda *a, **k: pytest.fail("Must not connect")
    )
    for url in (
        None,
        "",
        "postgresql://USER:PASSWORD@HOST:5432/DB?sslmode=require",
        "postgresql://u:p@localhost/db",
    ):
        assert probe.database_probe(url)["status"] == "blocked"


def test_driver_errors_never_reveal_url_credentials_or_exception_text(monkeypatch):
    from app.db import connection

    private = "private-database-credential"
    url = f"postgresql://user:{private}@db.example/db?sslmode=require"
    monkeypatch.setattr(connection, "validate_database_url", lambda: None)

    def fail(*a, **k):
        raise RuntimeError(url)

    monkeypatch.setattr(sqlalchemy, "create_engine", fail)
    result = probe.database_probe(url)
    assert result["status"] == "blocked"
    assert private not in json.dumps(result)
    assert "db.example" not in json.dumps(result)


def test_database_probe_is_read_only_and_checks_seed_and_hypertables(monkeypatch):
    from app.db import connection

    statements = []
    connect_args = {}

    class Result:
        def __init__(self, scalar=None, rows=()):
            self.scalar, self.rows = scalar, rows

        def scalar_one(self):
            return self.scalar

        def all(self):
            return self.rows

        def __iter__(self):
            return iter(self.rows)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, statement):
            sql = str(statement)
            statements.append(sql)
            if "hypertable_name" in sql:
                return Result(rows=[("observations",), ("alerts",), ("audit_events",)])
            if "pg_extension" in sql:
                return Result(scalar=True)
            if "GROUP BY" in sql:
                return Result(rows=[("crew", 1), ("supervisor", 1)])
            return Result(scalar=50)

    class Engine:
        disposed = False

        def connect(self):
            return Connection()

        def dispose(self):
            self.disposed = True

    engine = Engine()

    def create(*_a, **kwargs):
        connect_args.update(kwargs["connect_args"])
        return engine

    monkeypatch.setattr(connection, "validate_database_url", lambda: None)
    monkeypatch.setattr(sqlalchemy, "create_engine", create)
    monkeypatch.setattr(
        sqlalchemy,
        "inspect",
        lambda _: type("Inspector", (), {"get_table_names": lambda _: probe.TABLES})(),
    )
    result = probe.database_probe("postgresql://u:p@db.example/db?sslmode=require")
    assert result["status"] == "passed"
    assert result["connection"] == "verified_read_only_postgresql"
    assert "owner confirmation" in result["provider_account"]
    assert all(sql.startswith(("SELECT ", "SET TRANSACTION READ ONLY")) for sql in statements)
    assert "default_transaction_read_only=on" in connect_args["options"]
    assert connect_args["connect_timeout"] == 5
    assert engine.disposed


def test_missing_tables_are_blocked_without_ddl_or_seed(monkeypatch):
    from app.db import connection

    statements = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, sql):
            statements.append(str(sql))

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            pass

    monkeypatch.setattr(connection, "validate_database_url", lambda: None)
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *a, **k: Engine())
    monkeypatch.setattr(
        sqlalchemy, "inspect", lambda _: type("Inspector", (), {"get_table_names": lambda _: []})()
    )
    result = probe.database_probe("postgresql://u:p@db.example/db?sslmode=require")
    assert result["status"] == "blocked"
    assert result["missing_tables"] == sorted(probe.TABLES)
    assert statements == ["SET TRANSACTION READ ONLY"]


def test_canonical_validation_accepts_existing_fixtures_and_redacts_bad_payloads():
    sites = json.loads((ROOT / "frontend/src/fixtures/sites.json").read_text())
    details = json.loads((ROOT / "frontend/src/fixtures/site-detail.json").read_text())
    alerts = json.loads((ROOT / "frontend/src/fixtures/alerts.json").read_text())
    assert (
        probe.validate_payloads({"sites": sites, "details": [details], "alerts": alerts})["status"]
        == "passed"
    )
    result = probe.validate_payloads({"sites": [{"lat": "private-invalid-value"}]})
    assert result["status"] == "failed"
    assert "private-invalid-value" not in json.dumps(result)


def test_configuration_inspection_does_not_connect_seed_or_leak_private_values(
    monkeypatch, tmp_path
):
    from app.db import init

    for name in (
        "DATABASE_URL",
        "AUTH0_DOMAIN",
        "AUTH0_AUDIENCE",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "DEV_AUTH_BYPASS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init, "load_env_file", lambda: None)
    monkeypatch.setenv("GEMINI_API_KEY", "private-gemini-key")
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *a, **k: pytest.fail("No DB opt-in"))
    result = probe.inspect_backend({})
    assert not result["auth"]["dev_auth_bypass"]
    assert result["configuration"]["GEMINI_API_KEY"] == "set"
    assert result["database"]["status"] == "not_run"
    assert "private-gemini-key" not in json.dumps(result)
    assert "/api/sites" in result["routes_in_checkout"]


def test_private_token_prompt_refuses_noninteractive_echo_fallback():
    result = subprocess.run(
        [sys.executable, str(ROOT / "frontend/scripts/run-live-account-check.py")],
        input="",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Refusing an echoed token prompt" in result.stderr
    assert "Existing Auth0 crew access token" not in result.stderr
