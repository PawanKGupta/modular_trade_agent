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
    echo "WARNING: Database references missing revision. Pruning stale alembic_version rows..."
    python /app/tools/alembic_prune_stale_versions.py --apply
    FIX_EXIT=$?
    if [ "$FIX_EXIT" -eq 0 ]; then
      echo "Retrying migrations after prune..."
      python -m alembic upgrade heads || echo "WARNING: Migration failed after prune, continuing anyway..."
    else
      echo "ERROR: Could not prune stale Alembic versions."
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
