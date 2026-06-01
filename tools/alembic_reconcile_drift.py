#!/usr/bin/env python3
"""Reconcile Alembic when the DB schema exists but alembic_version is empty or missing.

Typical cause: Postgres restored/managed without stamping, so `upgrade` starts at
0001_initial and fails with DuplicateTable on `users`.

Safety: stamp `head` only if core application tables exist; fresh DBs (no `users`)
are left untouched. Opt out with ALEMBIC_SKIP_DRIFT_RECONCILE=1.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


CORE_TABLES = frozenset(
    {"users", "orders", "positions", "usersettings", "signals"}
)


def _public_table_names(engine) -> set[str]:
    from sqlalchemy import inspect  # noqa: PLC0415

    insp = inspect(engine)
    if engine.dialect.name == "postgresql":
        return set(insp.get_table_names(schema="public"))
    return set(insp.get_table_names())


def main() -> int:
    if os.getenv("ALEMBIC_SKIP_DRIFT_RECONCILE", "").strip().lower() in {"1", "true", "yes"}:
        return 0

    db_url = os.getenv("DB_URL", "").strip()
    if not db_url:
        return 0

    from sqlalchemy import create_engine, text  # noqa: PLC0415

    engine = create_engine(db_url, pool_pre_ping=False)
    try:
        tables = _public_table_names(engine)
        if "users" not in tables:
            return 0

        if not CORE_TABLES.issubset(tables):
            missing = sorted(CORE_TABLES - tables)
            print(
                f"alembic_reconcile: core tables missing ({missing}); "
                "not stamping (partial schema).",
                file=sys.stderr,
            )
            return 0

        with engine.connect() as conn:
            if engine.dialect.name == "postgresql":
                av_exists = conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name = 'alembic_version')"
                    )
                ).scalar()
            else:
                av_exists = "alembic_version" in tables

            rows = 0
            if av_exists:
                rows = conn.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar() or 0

        if av_exists and rows > 0:
            return 0

        root = Path(__file__).resolve().parents[1]
        print(
            "alembic_reconcile: existing schema with no Alembic revision "
            "(empty or missing alembic_version); stamping head.",
            file=sys.stderr,
        )
        r = subprocess.run(
            [sys.executable, "-m", "alembic", "stamp", "head"],
            cwd=root,
            env=os.environ.copy(),
            check=False,
        )
        if r.returncode != 0:
            print(f"alembic_reconcile: alembic stamp head failed ({r.returncode}).", file=sys.stderr)
            return r.returncode
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
