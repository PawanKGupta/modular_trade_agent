#!/usr/bin/env python3
"""
Remove alembic_version rows that reference migration files no longer in the repo.

Safe for production when the schema already reflects those migrations (only deletes
metadata rows in alembic_version; never drops tables or data).

Usage:
  python tools/alembic_prune_stale_versions.py          # dry-run (report only)
  python tools/alembic_prune_stale_versions.py --apply  # delete stale rows
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

def _repo_root() -> Path:
    for candidate in (Path.cwd(), Path(__file__).resolve().parents[1]):
        if (candidate / "alembic.ini").exists():
            return candidate
    raise SystemExit("ERROR: alembic.ini not found (run from repo root or /app)")


def _known_revisions() -> set[str]:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(_repo_root() / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    return {rev.revision for rev in script.walk_revisions()}


def _db_revisions(db_url: str) -> list[str]:
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        return [str(r[0]) for r in rows]
    finally:
        engine.dispose()


def _delete_stale(db_url: str, stale: list[str]) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            for version in stale:
                conn.execute(
                    text("DELETE FROM alembic_version WHERE version_num = :v"),
                    {"v": version},
                )
                print(f"Removed stale alembic_version row: {version}")
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete stale rows (default is dry-run only)",
    )
    args = parser.parse_args()

    db_url = os.getenv("DB_URL", "").strip()
    if not db_url:
        print("ERROR: DB_URL is not set", file=sys.stderr)
        return 1

    known = _known_revisions()
    db_rows = _db_revisions(db_url)
    stale = [v for v in db_rows if v not in known]
    valid = [v for v in db_rows if v in known]

    print(f"Known revisions in repo: {len(known)}")
    print(f"Rows in alembic_version: {db_rows}")
    print(f"Valid rows: {valid}")
    print(f"Stale rows (not in repo): {stale}")

    if not stale:
        print("Nothing to prune.")
        return 0

    if not args.apply:
        print("Dry-run only. Re-run with --apply to remove stale rows.")
        return 0

    _delete_stale(db_url, stale)
    print("Done. Run: python -m alembic current && python -m alembic upgrade heads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
