"""`python -m app.demo seed` restores the demo; `python -m app.demo strike N` replays lightning.
`python -m app.demo anomalies` clears crew reports and adds one demo site per anomaly type.

`python -m app.demo briefing-test` sets up the separate 6 PM briefing-test organization.

Run from backend/. Reads `DATABASE_URL`, `DEMO_CREW_USER_ID`, `DEMO_SUPERVISOR_USER_ID`,
`DEMO_EXTRA_CREW_USER_IDS`, and `BRIEFING_TEST_SUPERVISOR_USER_ID` from backend/.env.
User IDs are never printed.
"""

import argparse
import os
from datetime import UTC, datetime

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.db.connection import to_driver_url
from app.db.init import initialize_database, load_env_file
from app.demo.scenario import (
    PLACEHOLDER_CREW,
    PLACEHOLDER_SUPERVISOR,
    DemoAccounts,
    replay_lightning,
    seed_demo,
)


class DemoSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    demo_crew_user_id: str = ""
    demo_supervisor_user_id: str = ""
    demo_extra_crew_user_ids: str = ""  # comma-separated: teammates as crew
    briefing_test_supervisor_user_id: str = ""

    def accounts(self) -> DemoAccounts:
        return DemoAccounts(
            self.demo_crew_user_id.strip() or PLACEHOLDER_CREW,
            self.demo_supervisor_user_id.strip() or PLACEHOLDER_SUPERVISOR,
            tuple(i.strip() for i in self.demo_extra_crew_user_ids.split(",") if i.strip()),
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.demo", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed", help="remove the previous demo rows and restore the scenario")
    commands.add_parser(
        "briefing-test", help="set up the organization that checks the 6 PM briefing schedule"
    )
    commands.add_parser(
        "anomalies",
        help="add one demo site per anomaly; restore the Everglades wildlife demo",
    )
    commands.add_parser(
        "freshen", help="slide the demo sites' times to now (the server does this every round)"
    )
    strike = commands.add_parser("strike", help="replay one lightning step at the demo site")
    strike.add_argument("step", type=int, help="replay step, 1 to 3 (2 resets the countdown)")
    args = parser.parse_args(argv)

    load_env_file()
    try:
        _run(args)
    except Exception as exc:
        raise SystemExit(_redact(str(exc))) from None


def _run(args: argparse.Namespace) -> None:
    from app.db.session import get_session
    from app.outlook import get_event_outlook_service

    now = datetime.now(UTC)
    if args.command == "briefing-test":
        from app.demo.briefing_test import setup_briefing_test

        settings = DemoSettings()
        supervisor = settings.briefing_test_supervisor_user_id.strip()
        if supervisor in settings.accounts().user_ids:
            raise ValueError(
                "BRIEFING_TEST_SUPERVISOR_USER_ID must be a different account from the demo "
                "accounts (each account belongs to one organization)"
            )
        with get_session() as session:
            test = setup_briefing_test(session, supervisor, now)
        print(
            f"Briefing test ready: {test.site_name} ({test.site_id}). No stored briefing; "
            f"the schedule writes one at {test.next_run_local:%Y-%m-%d %H:%M %Z} (site time) "
            "on the backend that has BRIEFING_SCHEDULE_ENABLED."
        )
    elif args.command == "anomalies":
        from pathlib import Path

        from app.demo.anomalies import seed_anomalies
        from app.gemini.client import get_gemini_client

        initialize_database()
        # Outside the repository: backups hold crew reports, never committed.
        backups = Path(os.environ.get("DEMO_BACKUP_DIR", "~/foresite-demo-backups")).expanduser()
        with get_session() as session:
            results = seed_anomalies(
                session, now, backups, get_gemini_client(), get_event_outlook_service()
            )
        print(f"Demo anomalies seeded at {now:%Y-%m-%d %H:%M} UTC.")
        print(f"Removed rows were backed up in {backups}.")
        for r in results:
            print(f"  {r.site_id:24} {r.label:24} score {r.risk_score:.1f} ({r.risk_level})")
    elif args.command == "seed":
        initialize_database()
        accounts = DemoSettings().accounts()
        with get_session() as session:
            result = seed_demo(session, now, accounts, get_event_outlook_service())
        print(
            f"Demo restored at {now:%Y-%m-%d %H:%M} UTC: site {result.site_id}, "
            f"score {result.risk_score:.1f} ({result.risk_level}), "
            f"stop-work alert active, briefing {result.briefing.id} "
            f"({result.briefing.generated_by})."
        )
        if not result.accounts_linked:
            print(
                "Demo accounts are NOT linked: set DEMO_CREW_USER_ID and "
                "DEMO_SUPERVISOR_USER_ID (Auth0 user IDs) in backend/.env and run again."
            )
    elif args.command == "freshen":
        from app.demo.freshen import demo_briefing_sources, keep_demo_fresh

        with get_session() as session:
            moved = keep_demo_fresh(session, now, demo_briefing_sources())
        print(f"Moved {len(moved)} demo sites to {now:%Y-%m-%d %H:%M} UTC.")
        for site_id, delta in moved.items():
            print(f"  {site_id:24} +{delta}")
    else:
        with get_session() as session:
            transition = replay_lightning(session, args.step, now)
        print(f"Replayed lightning step {args.step}: {transition}.")


def _redact(message: str) -> str:
    secret = os.environ.get("DATABASE_URL", "")
    if secret:
        message = message.replace(secret, "DATABASE_URL")
        message = message.replace(to_driver_url(secret), "DATABASE_URL")
    return message


if __name__ == "__main__":
    main()
