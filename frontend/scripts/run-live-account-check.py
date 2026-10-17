"""Prompt privately for existing Auth0 access tokens and pipe them to the Node checker."""

import argparse
import getpass
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default=shutil.which("node"))
    parser.add_argument("--api-origin", default="http://127.0.0.1:8000")
    parser.add_argument("--frontend-origin", default="http://localhost:5173")
    parser.add_argument("--acknowledge", action="store_true")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise SystemExit("Use an interactive private terminal. Refusing an echoed token prompt.")
    if not args.node:
        raise SystemExit("Node 24 is required on PATH, or pass --node with its executable path.")
    frontend = Path(__file__).resolve().parents[1]
    tokens = {
        role: getpass.getpass(f"Existing Auth0 {role} access token (hidden; never saved): ")
        for role in ("crew", "supervisor")
    }
    if args.acknowledge:
        tokens["alert_id"] = getpass.getpass(
            "Dedicated active simulated alert ID for this crew (hidden): "
        )
    command = [
        args.node,
        str(frontend / "scripts/check-live-integration.mjs"),
        "--python",
        sys.executable,
        "--api-origin",
        args.api_origin,
        "--frontend-origin",
        args.frontend_origin,
        "--check-database",
        "--tokens-stdin",
    ]
    if args.acknowledge:
        command.append("--acknowledge")
    # subprocess gets only fixed options/paths in argv. No shell, credential env or temp file.
    result = subprocess.run(command, input=json.dumps(tokens), text=True, cwd=frontend, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
