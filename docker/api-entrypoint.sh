#!/bin/bash
# API container: reconcile Alembic drift, run migrations, start uvicorn.
set +e

cd /app || exit 1

# Seed /app/models from the image-baked fallback on first boot (empty volume).
# On subsequent restarts the volume already contains the canonical pkl so this is a no-op.
if [ -z "$(ls -A /app/models 2>/dev/null)" ] && [ -d /app/models_default ]; then
  echo "Seeding ML models volume from image defaults..."
  cp -r /app/models_default/. /app/models/
  echo "ML models seeded."
fi

# Seed the ML training dataset into the trading_data volume. Unlike /app/models this volume
# also holds the runtime DB, so we never gate on emptiness. We copy a dataset when it is
# absent, AND refresh it when the image-baked copy has changed (e.g. a new schema or extra
# label columns after an upgrade) so training never runs on a stale volume copy — the cause
# of "price regressor requires target column 'max_favorable_pct_20d'" after upgrades. The
# previous volume copy is backed up before a refresh. Failures must not block API startup.
_dataset_differs() {
  # True (0) when the two files differ or cannot be compared. Prefer cmp; fall back to
  # byte size via wc (both safe on the slim base image) when cmp is unavailable.
  if command -v cmp >/dev/null 2>&1; then
    ! cmp -s "$1" "$2"
  else
    [ "$(wc -c < "$1" 2>/dev/null)" != "$(wc -c < "$2" 2>/dev/null)" ]
  fi
}
if [ -d /app/data_default/training ]; then
  mkdir -p /app/data/training
  for f in /app/data_default/training/*.csv; do
    [ -e "$f" ] || continue
    dest="/app/data/training/$(basename "$f")"
    if [ ! -f "$dest" ]; then
      cp "$f" "$dest" && echo "Seeded ML training dataset: $dest" || echo "WARN: could not seed $dest"
    elif _dataset_differs "$f" "$dest"; then
      cp "$dest" "$dest.bak.$(date +%Y%m%d%H%M%S)" 2>/dev/null || true
      cp "$f" "$dest" \
        && echo "Refreshed ML training dataset from image default (previous copy backed up): $dest" \
        || echo "WARN: could not refresh $dest"
    fi
  done
fi

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
