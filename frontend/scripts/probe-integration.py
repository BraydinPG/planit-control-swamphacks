"""Redacted, read-only inspection of the existing backend; never initialize or seed."""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
TABLES = (
    "sites",
    "organizations",
    "teams",
    "memberships",
    "observations",
    "alerts",
    "acknowledgements",
    "crew_reports",
    "hazard_notices",
)


def present(value):
    if not value or not str(value).strip():
        return "missing"
    if any(
        marker in str(value).lower()
        for marker in ("<", ">", "your-tenant", "your-client", "user:password@", "@host:")
    ):
        return "placeholder"
    return "set"


def domain(value):
    return (value or "").removeprefix("https://").removeprefix("http://").rstrip("/").lower()


def database_probe(url):
    if present(url) != "set":
        return {"status": "blocked", "reason": "DATABASE_URL missing or placeholder"}
    if (urlparse(url).hostname or "").lower() in {
        "localhost",
        "127.0.0.1",
        "::1",
        "host.docker.internal",
    }:
        return {"status": "blocked", "reason": "Local database is not Tiger Data acceptance"}
    engine = None
    try:
        from app.db.connection import to_driver_url, validate_database_url
        from sqlalchemy import create_engine, inspect, text

        validate_database_url()
        engine = create_engine(
            to_driver_url(url),
            connect_args={
                "connect_timeout": 5,
                "options": "-c default_transaction_read_only=on -c statement_timeout=4000",
            },
        )
        with engine.connect() as connection:
            # No schema creation, migration, writes or seed calls are permitted here.
            connection.execute(text("SET TRANSACTION READ ONLY"))
            missing = sorted(set(TABLES) - set(inspect(connection).get_table_names()))
            if missing:
                return {
                    "status": "blocked",
                    "reason": "Required tables missing",
                    "missing_tables": missing,
                }
            counts = {
                table: connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
                for table in TABLES
            }
            eia = connection.execute(
                text(
                    "SELECT count(*) FROM sites WHERE id ~ '^eia860m-[A-Z]{2}-[0-9]+$' AND lat BETWEEN -90 AND 90 AND lon BETWEEN -180 AND 180"
                )
            ).scalar_one()
            assigned = connection.execute(
                text("SELECT count(*) FROM teams WHERE site_id IS NOT NULL")
            ).scalar_one()
            roles = dict(
                connection.execute(
                    text("SELECT role, count(*) FROM memberships GROUP BY role")
                ).all()
            )
            linked = dict(
                connection.execute(
                    text(
                        "SELECT m.role, count(*) FROM memberships m JOIN organizations o ON o.id=m.organization_id LEFT JOIN teams t ON t.id=m.team_id WHERE (m.role='supervisor' AND m.team_id IS NULL) OR (m.role='crew' AND t.organization_id=m.organization_id AND t.site_id IS NOT NULL) GROUP BY m.role"
                    )
                ).all()
            )
            timescale = bool(
                connection.execute(
                    text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='timescaledb')")
                ).scalar_one()
            )
            hypertables = []
            if timescale:
                hypertables = [
                    row[0]
                    for row in connection.execute(
                        text(
                            "SELECT hypertable_name FROM timescaledb_information.hypertables WHERE hypertable_schema='public' AND hypertable_name IN ('observations','alerts','audit_events')"
                        )
                    )
                ]
            seeded = (
                eia >= 50
                and assigned > 0
                and all(linked.get(role, 0) > 0 for role in ("crew", "supervisor"))
            )
            return {
                "status": "passed" if seeded and len(hypertables) == 3 else "blocked",
                "connection": "verified_read_only_postgresql",
                "provider_account": "Tiger Data account provenance requires owner confirmation",
                "counts": counts,
                "eia_id_coordinate_rows": eia,
                "assigned_teams": assigned,
                "membership_roles": {role: roles.get(role, 0) for role in ("crew", "supervisor")},
                "linked_roles": {role: linked.get(role, 0) for role in ("crew", "supervisor")},
                "required_hypertables": len(hypertables),
                "seeded": seeded,
            }
    except Exception:  # noqa: BLE001 - diagnostic boundary must not expose driver secrets.
        # Driver/validation exceptions can contain hosts, passwords, statements or row values.
        return {
            "status": "blocked",
            "reason": "Database validation/connection/query failed; inspect privately with owner",
        }
    finally:
        if engine is not None:
            engine.dispose()


def inspect_backend(frontend, check_database=False):
    from app.db.init import load_env_file
    from app.ingestion.settings import get_ingestion_settings
    from app.security.settings import AuthSettings

    load_env_file()
    settings = AuthSettings()
    feeds = get_ingestion_settings()
    names = (
        "DATABASE_URL",
        "AUTH0_DOMAIN",
        "AUTH0_AUDIENCE",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "VULTR_OBJECT_STORAGE_ENDPOINT",
        "VULTR_OBJECT_STORAGE_ACCESS_KEY",
        "VULTR_OBJECT_STORAGE_SECRET_KEY",
        "VULTR_OBJECT_STORAGE_BUCKET",
    )
    values = {key: present(os.environ.get(key)) for key in names}
    auth = {
        "configured": settings.configured,
        "dev_auth_bypass": settings.dev_auth_bypass,
        "domain_matches_spa": bool(
            settings.auth0_domain
            and domain(settings.auth0_domain) == domain(frontend.get("VITE_AUTH0_DOMAIN"))
        ),
        "audience_matches_spa": bool(
            settings.auth0_audience
            and settings.auth0_audience == frontend.get("VITE_AUTH0_AUDIENCE")
        ),
    }
    from app.main import app

    routes = {
        path: sorted(
            method.upper()
            for method in operations
            if method in {"get", "post", "put", "patch", "delete"}
        )
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/api/")
    }
    database = (
        database_probe(os.environ.get("DATABASE_URL"))
        if check_database
        else {
            "status": "not_run",
            "reason": "Use --check-database for bounded read-only inspection",
        }
    )
    return {
        "status": "inspected",
        "configuration": values,
        "auth": auth,
        "routes_in_checkout": routes,
        "database": database,
        "ingestion": {
            "background_refresh_enabled": getattr(feeds, "feed_refresh_enabled", False),
            "nws_user_agent": present(feeds.nws_user_agent),
            "note": "Settings inspection does not start the refresh loop or fetch feeds",
        },
    }


def validate_payloads(payload):
    from app.schemas import Alert, CrewReport, SiteDetail, SiteSummary

    try:
        for key, schema in (
            ("sites", SiteSummary),
            ("details", SiteDetail),
            ("alerts", Alert),
            ("reports", CrewReport),
        ):
            for row in payload.get(key, []):
                schema.model_validate(row)
        return {
            "status": "passed",
            "counts": {
                key: len(payload.get(key, [])) for key in ("sites", "details", "alerts", "reports")
            },
        }
    except Exception:  # noqa: BLE001 - schema exceptions include raw private input values.
        return {
            "status": "failed",
            "reason": "Response did not validate against canonical backend schemas",
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-database", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "backend"))
    os.chdir(ROOT / "backend")
    try:
        payload = json.loads(sys.stdin.read(8 * 1024 * 1024) or "{}")
        result = (
            validate_payloads(payload)
            if args.validate
            else inspect_backend(payload, args.check_database)
        )
    except Exception:  # noqa: BLE001 - redact settings/dependency exceptions at CLI boundary.
        result = {
            "status": "blocked",
            "reason": "Backend dependencies or settings unavailable; use documented backend Python environment",
        }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
