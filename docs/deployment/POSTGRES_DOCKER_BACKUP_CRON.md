# PostgreSQL (Docker) — scheduled backup, cron, and restore

**Purpose:** Back up the `tradeagent` Postgres database that runs in Docker (`tradeagent-db`) and restore it when needed, without putting secrets in shell history.

**Audience:** Operators deploying with `docker/docker-compose.yml` and production overrides (`docker-compose.prod.yml`).

---

## 1. Overview

- **Method:** `pg_dump` from **inside** the `postgres:15-alpine` container, compressed with **gzip** on the host.
- **Credentials:** The script uses `POSTGRES_USER` and `POSTGRES_DB` from the **container environment** (set by Compose), so the **host** does not need `PGPASSWORD` in cron.
- **Script (repo):** `docker/scripts/backup_postgres_docker.sh`
- **Default output:** `~/backups/tradeagent-postgres/tradeagent_YYYYMMDD_HHMMSS.sql.gz`
- **Retention:** Default **14 days** of files (oldest removed automatically).

---

## 2. Prerequisites

- Docker running; **`tradeagent-db` container** running (`docker ps` shows it).
- Script **executable** on the server:
  `chmod +x /home/ubuntu/modular_trade_agent/docker/scripts/backup_postgres_docker.sh`
  (adjust path if your clone lives elsewhere).

---

## 3. Environment variables (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_BACKUP_CONTAINER` | `tradeagent-db` | DB container name |
| `POSTGRES_BACKUP_DIR` | `$HOME/backups/tradeagent-postgres` | Where `.sql.gz` files are written |
| `POSTGRES_BACKUP_RETAIN_DAYS` | `14` | Delete backups older than this many days |

---

## 4. Cron: daily backup (example 02:15)

Edit the **ubuntu** user’s crontab (or the user that owns the repo and Docker access):

```bash
crontab -e
```

Add one line (adjust paths to match your home and clone):

```cron
15 2 * * * /home/ubuntu/modular_trade_agent/docker/scripts/backup_postgres_docker.sh >>/var/log/tradeagent-pg-backup.log 2>&1
```

**Log file (once):**

```bash
sudo touch /var/log/tradeagent-pg-backup.log
sudo chown ubuntu:ubuntu /var/log/tradeagent-pg-backup.log
```

**Verify:**

```bash
crontab -l
```

**Manual test (no cron):**

```bash
/home/ubuntu/modular_trade_agent/docker/scripts/backup_postgres_docker.sh
ls -la ~/backups/tradeagent-postgres/
```

**Saving in nano (crontab -e):** `Ctrl+O` → **Enter** to confirm the temp path → `Ctrl+X` to exit. You may see: `crontab: installing new crontab`.

---

## 5. What gets backed up

- Logical dump of the **`tradeagent`** database (schema + data for that DB).
- **Not** a raw copy of the Docker volume; that is a separate concern (e.g. block-volume snapshots in Oracle Cloud).

---

## 6. Restore (disaster recovery or migration)

**Warning:** A full restore overwrites the target database. Prefer testing on a **non-production** copy first.

1. Ensure **`tradeagent-db` is up** and points at the same DB you intend to replace (or use a new empty DB and migrate).

2. Decompress and pipe into `psql` (example paths):

   ```bash
   zcat /home/ubuntu/backups/tradeagent-postgres/tradeagent_YYYYMMDD_HHMMSS.sql.gz | \
     docker exec -i tradeagent-db psql -U trader -d tradeagent
   ```

3. If `psql` reports errors about existing objects, you may need a **clean** database or a dump taken with options suitable for your workflow (e.g. drop/recreate in a maintenance window). Consult PostgreSQL documentation for your risk tolerance.

4. **Restart the API** if the app caches connections:
   `docker restart tradeagent-api` (names may differ).

**Credentials:** `trader` / database `tradeagent` match the default in `docker/docker-compose.yml`; change flags if you use different `POSTGRES_*` values.

---

## 7. Freeing disk (Docker) without losing backups

- Prefer **`docker system prune`** and **`docker image prune`** **without** `--volumes` so **named** volumes (Postgres data) are not removed.
- **Avoid** `docker volume prune` and `docker system prune --volumes` on production until you are sure which volumes are disposable and you have a **recent** `pg_dump` (or OCI block snapshot).

---

## 8. Related

- Compose DB service: `docker/docker-compose.yml` — `tradeagent-db`, volume `postgres_data` (named, e.g. `docker_postgres_data` on the host under snap Docker).
- Project documentation standards: `docs/DOCUMENTATION_RULES.md`

---

**Last updated:** 2026-04-28
