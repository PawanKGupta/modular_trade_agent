#!/usr/bin/env bash
# Nightly/scheduled logical backup of tradeagent PostgreSQL in Docker.
# Run on the host (not inside a container). Requires: docker, container name tradeagent-db.
#
# Crontab example (daily 02:15):
#   15 2 * * * /home/ubuntu/modular_trade_agent/docker/scripts/backup_postgres_docker.sh >>/var/log/tradeagent-pg-backup.log 2>&1
#
# The postgres image already sets POSTGRES_USER / POSTGRES_DB inside the container; we use
# them so the password is not required on the host command line.
set -euo pipefail

CONTAINER_NAME="${POSTGRES_BACKUP_CONTAINER:-tradeagent-db}"
BACKUP_DIR="${POSTGRES_BACKUP_DIR:-$HOME/backups/tradeagent-postgres}"
RETAIN_DAYS="${POSTGRES_BACKUP_RETAIN_DAYS:-14}"
STAMP=$(date -u +%Y%m%d_%H%M%S)
FILENAME="tradeagent_${STAMP}.sql.gz"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
  echo "ERROR: container '${CONTAINER_NAME}' is not running. Skip backup." >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"
OUT="${BACKUP_DIR}/${FILENAME}"
TMP="${OUT}.part"

# pg_dump with credentials from inside the DB container; write to .part then mv on success
docker exec "${CONTAINER_NAME}" sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl' | gzip -c > "${TMP}"
mv -f "${TMP}" "${OUT}"
chmod 600 "${OUT}" 2>/dev/null || true

# Drop backups older than RETAIN_DAYS
find "${BACKUP_DIR}" -type f -name 'tradeagent_*.sql.gz' -mtime +"${RETAIN_DAYS}" -print -delete 2>/dev/null || true

echo "$(date -Iseconds) OK ${OUT} $(du -h "${OUT}" | cut -f1)"
