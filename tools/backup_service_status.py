#!/usr/bin/env python3
"""
Backup unified and individual service running state before redeploy.

Writes ``data/service_restore_snapshot.json`` (and a rolling history) so API
startup can auto-restore services after container restart.

Usage (from repo root, inside API container or with DB reachable):

    python tools/backup_service_status.py

Before production redeploy:

    docker exec tradeagent-api python /app/tools/backup_service_status.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Repo root on PYTHONPATH when run from container /app
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.application.services.service_restore_snapshot import (  # noqa: E402
    build_snapshot,
    load_snapshot,
    persist_service_restore_snapshot,
    snapshot_path,
)
from src.infrastructure.db.session import SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backup running service status for post-redeploy auto-restore."
    )
    parser.add_argument(
        "--print",
        action="store_true",
        dest="print_json",
        help="Print snapshot JSON to stdout after saving",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build snapshot and print only; do not write files",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.dry_run:
            snapshot = build_snapshot(db, source="cli_dry_run")
            print(json.dumps(snapshot, indent=2, sort_keys=True))
            return 0

        path = persist_service_restore_snapshot(db, source="cli_backup")
        if path is None:
            print("ERROR: Failed to save service restore snapshot", file=sys.stderr)
            return 1

        if args.print_json:
            data = load_snapshot(path) or build_snapshot(db, source="cli_backup")
            print(json.dumps(data, indent=2, sort_keys=True))
        else:
            print(f"OK: service restore snapshot saved to {path}")
            print(f"     (default path: {snapshot_path()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
