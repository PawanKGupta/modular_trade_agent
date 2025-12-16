# Full Symbols Migration - Docker Setup Guide

**Setting up Docker environment for migration testing.**

## Database Port Access

The Docker database container may not expose port 5432 to the host by default. You have two options:

### Option 1: Expose Port 5432 (Recommended for Testing)

Add port mapping to `docker/docker-compose.yml`:

```yaml
tradeagent-db:
  image: postgres:15-alpine
  container_name: tradeagent-db
  restart: unless-stopped
  ports:
    - "5432:5432"  # Expose PostgreSQL port to host
  environment:
    - POSTGRES_DB=tradeagent
    - POSTGRES_USER=trader
    - POSTGRES_PASSWORD=changeme
  # ... rest of config
```

Then restart the database:
```bash
docker-compose -f docker/docker-compose.yml restart tradeagent-db
```

### Option 2: Use Docker Exec (No Port Exposure Needed)

Run migration commands inside the container:

```bash
# Check current state
docker exec -it tradeagent-db psql -U trader -d tradeagent -c "SELECT COUNT(*) as total, COUNT(CASE WHEN symbol LIKE '%-EQ' OR symbol LIKE '%-BE' OR symbol LIKE '%-BL' OR symbol LIKE '%-BZ' THEN 1 END) as full_symbols FROM positions;"

# Run migration using Alembic inside container
docker exec -it tradeagent-db bash -c "cd /app && alembic upgrade head"
```

## Quick Setup Steps

1. **Ensure database is running:**
   ```bash
   docker ps | grep tradeagent-db
   ```

2. **Install Python dependencies:**
   ```bash
   .venv\Scripts\activate  # Windows
   pip install psycopg2-binary alembic
   ```

3. **Choose connection method:**
   - **Option A**: Expose port 5432 (see above)
   - **Option B**: Use docker exec (see scripts/run_migration_docker_exec.sh)

4. **Run test script:**
   ```bash
   python scripts/test_migration_docker.py
   ```

## Alternative: Run Migration Inside Container

If you can't expose the port, you can run the migration script inside the container:

```bash
# Copy script to container
docker cp scripts/test_migration_docker.py tradeagent-db:/tmp/test_migration.py

# Run inside container
docker exec -it tradeagent-db python3 /tmp/test_migration.py --db-url "postgresql+psycopg2://trader:changeme@localhost:5432/tradeagent"
```

## Verification

After setup, verify connection:

```bash
# Test connection (if port is exposed)
python -c "from sqlalchemy import create_engine; engine = create_engine('postgresql+psycopg2://trader:changeme@localhost:5432/tradeagent'); print('Connected!')"

# Or test from inside container
docker exec -it tradeagent-db psql -U trader -d tradeagent -c "SELECT version();"
```
