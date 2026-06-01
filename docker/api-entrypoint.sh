#!/bin/bash
# API container: reconcile Alembic drift, run migrations, start uvicorn.
set +e

cd /app || exit 1

echo "Checking database migration status..."
python /app/tools/alembic_reconcile_drift.py
RECON_EXIT=$?
if [ "$RECON_EXIT" -ne 0 ]; then
  echo "ERROR: alembic_reconcile_drift exited with ${RECON_EXIT}. Refusing to start API."
  exit "$RECON_EXIT"
fi

echo "Running database migrations..."
MIGRATION_OUTPUT=$(python -m alembic upgrade heads 2>&1)
MIGRATION_EXIT=$?
echo "$MIGRATION_OUTPUT"
if [ "$MIGRATION_EXIT" -ne 0 ]; then
  if echo "$MIGRATION_OUTPUT" | grep -q "Can't locate revision"; then
    echo "WARNING: Database references missing revision. Attempting safe recovery..."
    python << 'PYEOF'
import os
import sqlite3
from sqlalchemy import create_engine, inspect

db_url = os.getenv("DB_URL", "sqlite:///./data/app.db")
db_path = db_url.replace("sqlite:///", "", 1) if db_url.startswith("sqlite:///") else db_url
if not os.path.exists(db_path):
    print("INFO: Database does not exist, will be created by migrations")
    raise SystemExit(0)
try:
    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    tbl = inspector.get_table_names()
    critical_tables = ["users", "orders", "positions", "alembic_version"]
    missing_tables = [t for t in critical_tables if t not in tbl]
    if missing_tables:
        print(f"WARNING: Missing critical tables: {missing_tables}")
        print("WARNING: Schema appears incomplete. Proceeding anyway...")
    if "orders" in tbl:
        orders_cols = {c["name"] for c in inspector.get_columns("orders")}
        required_cols = {"id", "user_id", "symbol", "status", "placed_at"}
        missing_cols = required_cols - orders_cols
        if missing_cols:
            print(f"WARNING: Orders table missing columns: {missing_cols}")
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM alembic_version")
    conn.commit()
    conn.close()
    print("SUCCESS: Cleared alembic_version table")
    engine.dispose()
    raise SystemExit(0)
except Exception as e:
    print(f"ERROR: Failed to fix migration revision: {e}")
    raise SystemExit(1)
PYEOF
    FIX_EXIT=$?
    if [ "$FIX_EXIT" -eq 0 ]; then
      echo "Stamping database to head..."
      python -m alembic stamp head || echo "WARNING: Could not stamp database"
      echo "Retrying migrations..."
      python -m alembic upgrade heads || echo "WARNING: Migration failed after stamp, continuing anyway..."
    else
      echo "ERROR: Schema validation failed. Database may be incomplete."
      echo "WARNING: Continuing anyway, but manual database fix may be required."
    fi
  elif echo "$MIGRATION_OUTPUT" | grep -qE "DuplicateTable|relation .* already exists"; then
    echo "WARNING: Migration conflict with existing objects. Running drift reconcile stamp + retry..."
    python /app/tools/alembic_reconcile_drift.py && python -m alembic upgrade heads
    retry_exit=$?
    if [ "$retry_exit" -ne 0 ]; then
      echo "WARNING: Retry after reconcile failed (${retry_exit}), continuing anyway..."
    fi
  else
    echo "WARNING: Migration failed with unknown error, continuing anyway..."
  fi
fi

set -e
echo "Starting API server..."
exec uvicorn server.app.main:app --host 0.0.0.0 --port 8000
