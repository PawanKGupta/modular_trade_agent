#!/usr/bin/env python3
"""Compare live database tables/columns to SQLAlchemy models (src.infrastructure.db.models).

Use after restoring or recreating a DB volume to confirm migrations match the ORM.

  DB_URL=postgresql://... python tools/verify_db_schema.py

  docker exec tradeagent-api python /app/tools/verify_db_schema.py

Exit codes: 0 = OK, 1 = schema drift, 2 = configuration/connection error.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _schema_for_dialect(dialect_name: str) -> str | None:
    return "public" if dialect_name == "postgresql" else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only print errors (missing tables/columns).",
    )
    args = parser.parse_args()

    db_url = os.getenv("DB_URL", "").strip()
    if not db_url:
        print("ERROR: DB_URL is not set.", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        from sqlalchemy import create_engine, inspect, text  # noqa: PLC0415
    except ImportError as e:
        print(f"ERROR: SQLAlchemy not available: {e}", file=sys.stderr)
        return 2

    import src.infrastructure.db.models  # noqa: F401, PLC0415
    from src.infrastructure.db.base import Base  # noqa: PLC0415

    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        insp = inspect(engine)
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}", file=sys.stderr)
        return 2

    dialect = engine.dialect.name
    schema = _schema_for_dialect(dialect)

    def table_exists(name: str) -> bool:
        try:
            return insp.has_table(name, schema=schema)
        except TypeError:
            return insp.has_table(name)

    def column_names_for(table: str) -> set[str]:
        try:
            cols = insp.get_columns(table, schema=schema)
        except Exception:
            cols = insp.get_columns(table)
        return {c["name"] for c in cols}

    missing_tables: list[str] = []
    missing_columns: list[tuple[str, str]] = []

    for table_name in sorted(Base.metadata.tables.keys()):
        tbl = Base.metadata.tables[table_name]
        if not table_exists(table_name):
            missing_tables.append(table_name)
            continue

        expected = {c.name for c in tbl.columns}
        actual = column_names_for(table_name)
        for col in sorted(expected - actual):
            missing_columns.append((table_name, col))

    # Informational: Alembic bookkeeping (not an ORM table)
    alembic_ok = True
    if dialect == "postgresql":
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name = 'alembic_version')"
                    )
                ).scalar()
                alembic_ok = bool(row)
        except Exception:
            alembic_ok = False
    else:
        alembic_ok = table_exists("alembic_version")

    engine.dispose()

    if not args.quiet:
        print(f"Dialect: {dialect}")
        print(f"ORM tables in metadata: {len(Base.metadata.tables)}")
        print(f"alembic_version table present: {alembic_ok}")
        print()

    if missing_tables:
        print("MISSING TABLES (in models, not in database):", file=sys.stderr)
        for t in missing_tables:
            print(f"  - {t}", file=sys.stderr)
        print(file=sys.stderr)

    if missing_columns:
        print("MISSING COLUMNS (in models, not in database):", file=sys.stderr)
        for table, col in missing_columns:
            print(f"  - {table}.{col}", file=sys.stderr)
        print(file=sys.stderr)

    if not alembic_ok and not args.quiet:
        print(
            "WARNING: alembic_version is missing; run `alembic upgrade heads` "
            "before relying on migrations.",
            file=sys.stderr,
        )

    if missing_tables or missing_columns:
        print(
            "Fix: apply migrations from an app container "
            "(`python -m alembic upgrade heads`) or restore a full DB backup.",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        print("OK: All ORM tables and columns exist in the database.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
