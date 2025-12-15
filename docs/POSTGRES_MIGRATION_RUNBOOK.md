# Postgres Migration Runbook (Docker Host)

Purpose: migrate the app from SQLite to PostgreSQL on another Docker server using the working steps already validated.

## Prerequisites
- Docker + Docker Compose installed on target host.
- Repo checked out (or updated) on the host.
- Network can pull container images.
- Postgres image available (`postgres:15` assumed from compose).

## 0) Stop the stack
```
cd /path/to/modular_trade_agent
docker compose -f docker/docker-compose.yml down
```

## 1) Backup existing SQLite (inside the old stack)
```
docker compose -f docker/docker-compose.yml up -d api-server
docker exec tradeagent-api sh -c "cp /app/data/app.db /app/data/app.db.bak.$(date -u +%Y%m%d%H%M%S)"
docker cp tradeagent-api:/app/data/app.db.bak.* ./data/   # optional: pull backup to host
docker compose -f docker/docker-compose.yml down
```

## 2) Ensure compose is configured for Postgres
- In `docker/docker-compose.yml`:
  - Service `tradeagent-db` present with env:
    - `POSTGRES_USER=trader`
    - `POSTGRES_PASSWORD=changeme`
    - `POSTGRES_DB=tradeagent`
  - Named volume `postgres_data` mounted to `/var/lib/postgresql/data`.
  - `api-server` `DB_URL` set to `postgresql+psycopg2://trader:changeme@tradeagent-db:5432/tradeagent`.
  - `api-server` depends_on `tradeagent-db` with healthcheck.

## 3) Start Postgres only
```
docker compose -f docker/docker-compose.yml up -d tradeagent-db
docker exec tradeagent-db pg_isready -U trader -d tradeagent
```

## 4) Reset Postgres schema (clean slate)
```
docker exec -e PGPASSWORD=changeme tradeagent-db psql -U trader -c "ALTER DATABASE tradeagent OWNER TO trader;"
docker exec -e PGPASSWORD=changeme tradeagent-db psql -U trader -c "DROP DATABASE IF EXISTS tradeagent;"
docker exec -e PGPASSWORD=changeme tradeagent-db psql -U trader -c "CREATE DATABASE tradeagent OWNER trader;"
```

## 5) Initialize schema + alembic_version
Run inside the API container (with Postgres `DB_URL` already set in compose):
```
docker compose -f docker/docker-compose.yml up -d api-server

docker exec tradeagent-api python - <<'PY'
from sqlalchemy import create_engine, text
from src.infrastructure.db import Base
from src.infrastructure.db.session import get_db_url

engine = create_engine(get_db_url())
Base.metadata.create_all(engine)  # create tables

REV = "20251213_add_failed_status_to_signalstatus"
with engine.begin() as conn:
    conn.exec_driver_sql("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version') THEN
            CREATE TABLE alembic_version (version_num VARCHAR(128) NOT NULL);
        END IF;
    END$$;
    """)
    conn.exec_driver_sql("TRUNCATE alembic_version;")
    conn.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES (:rev)", {"rev": REV})
PY
```

## 6) Migrate data from SQLite backup to Postgres
- Copy the SQLite backup into the api container if not present:
```
docker cp ./data/app.db.bak.* tradeagent-api:/app/data/app.db.bak
```
- Run a lightweight Python migrator inside the api container:
```
docker exec tradeagent-api python - <<'PY'
import sqlite3
from sqlalchemy import create_engine, text
from src.infrastructure.db.session import get_db_url

sqlite_path = "/app/data/app.db.bak"
engine = create_engine(get_db_url())

def copy_table(table):
    with sqlite3.connect(sqlite_path) as src, engine.begin() as tgt:
        cols = [r[1] for r in src.execute(f"PRAGMA table_info({table})")]
        rows = list(src.execute(f"SELECT * FROM {table}"))
        if not rows:
            return
        placeholders = ", ".join([f":{c}" for c in cols])
        insert_sql = text(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})")
        for row in rows:
            tgt.execute(insert_sql, dict(zip(cols, row)))

tables = [
    "users",
    "user_profile",
    "service_status",
    "service_task_execution",
    "error_logs",
    "signals",
    "signal_status",
    # add any other business tables that exist in the SQLite backup
]
for t in tables:
    try:
        copy_table(t)
    except Exception as exc:
        print(f"skip {t}: {exc}")

# Reset sequences for serial IDs
with engine.begin() as conn:
    seqs = conn.execute(text("""
        SELECT sequence_name FROM information_schema.sequences
        WHERE sequence_schema = 'public'
    """)).scalars().all()
    for seq in seqs:
        table = seq.replace("_id_seq","").replace("_seq","")
        conn.execute(text(f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM {table}),0)+1);"))
PY
```

## 7) Restart full stack on Postgres
```
docker compose -f docker/docker-compose.yml restart api-server web-frontend
```

## 8) Smoke verification
```
docker exec tradeagent-api curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health   # expect 200
# Perform a real login using correct JSON body via UI or API
```
- Check app functions (dashboard load, start service, logs view).

## 9) Rollback (if needed)
- Stop stack: `docker compose down`
- Restore SQLite file to `/app/data/app.db` inside api container from the backup.
- Revert `DB_URL` in compose to SQLite and `docker compose up -d api-server web-frontend`.
