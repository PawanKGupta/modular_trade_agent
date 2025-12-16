# PostgreSQL Migration Troubleshooting

## Container Restarting Issue

If you see this error:
```
Error response from daemon: Container ... is restarting, wait until the container is running
```

### Root Cause

The API server container is configured to use PostgreSQL (`DB_URL=postgresql+psycopg2://...`), but:
1. The database might not exist yet
2. The database might not be ready
3. The connection might be failing

### Solution 1: Check Container Logs

First, check why the container is restarting:

```bash
# Check API server logs
docker logs tradeagent-api --tail 100

# Check database logs
docker logs tradeagent-db --tail 50

# Check container status
docker ps -a | grep tradeagent
```

### Solution 2: Wait for Database to be Ready

The database needs to be ready before the API server can start:

```bash
# Start only the database first
docker-compose -f docker/docker-compose.yml up -d tradeagent-db

# Wait for database to be ready (check healthcheck)
docker exec tradeagent-db pg_isready -U trader -d tradeagent

# If database doesn't exist, create it
docker exec -e PGPASSWORD=changeme tradeagent-db psql -U trader -c "CREATE DATABASE tradeagent;" || echo "Database already exists"

# Now start the API server
docker-compose -f docker/docker-compose.yml up -d api-server

# Check if it's running
docker ps | grep tradeagent-api
```

### Solution 3: Temporarily Use SQLite for Backup (If Migrating FROM SQLite)

If you're migrating FROM SQLite and need to backup first, temporarily switch to SQLite:

```bash
# Stop containers
docker-compose -f docker/docker-compose.yml down

# Temporarily modify docker-compose.yml to use SQLite
# Change DB_URL from:
#   - DB_URL=postgresql+psycopg2://trader:changeme@tradeagent-db:5432/tradeagent
# To:
#   - DB_URL=sqlite:///./data/app.db

# Or use environment override:
docker-compose -f docker/docker-compose.yml run --rm -e DB_URL=sqlite:///./data/app.db api-server sh -c "cp /app/data/app.db /app/data/app.db.bak.\$(date -u +%Y%m%d%H%M%S)"

# Or manually copy if the file exists on host
cp ~/modular_trade_agent/data/app.db ~/modular_trade_agent/data/app.db.bak.$(date -u +%Y%m%d%H%M%S)

# Restore PostgreSQL DB_URL in docker-compose.yml
# Then continue with migration steps
```

### Solution 4: Fix Database Connection Issues

If the database exists but connection fails:

```bash
# Check if database is accessible
docker exec -e PGPASSWORD=changeme tradeagent-db psql -U trader -d tradeagent -c "SELECT version();"

# Check network connectivity
docker exec tradeagent-api ping -c 3 tradeagent-db

# Verify environment variables
docker exec tradeagent-api env | grep DB_URL
```

### Solution 5: Initialize Database Schema First

If starting fresh with PostgreSQL:

```bash
# Start database
docker-compose -f docker/docker-compose.yml up -d tradeagent-db

# Wait for database to be ready
sleep 5

# Create database if it doesn't exist
docker exec -e PGPASSWORD=changeme tradeagent-db psql -U trader -c "CREATE DATABASE tradeagent;" || echo "Database already exists"

# Start API server (it will run migrations automatically)
docker-compose -f docker/docker-compose.yml up -d api-server

# Check logs to see if migrations ran successfully
docker logs tradeagent-api --tail 50
```

## Common Issues

### Issue: "database does not exist"

**Solution**: Create the database first:
```bash
docker exec -e PGPASSWORD=changeme tradeagent-db psql -U trader -c "CREATE DATABASE tradeagent;"
```

### Issue: "connection refused"

**Solution**: Wait for database to be ready:
```bash
docker exec tradeagent-db pg_isready -U trader
```

### Issue: "password authentication failed"

**Solution**: Verify credentials match in docker-compose.yml:
- `POSTGRES_USER=trader`
- `POSTGRES_PASSWORD=changeme`
- `DB_URL=postgresql+psycopg2://trader:changeme@tradeagent-db:5432/tradeagent`

### Issue: "relation does not exist"

**Solution**: Run migrations:
```bash
docker exec tradeagent-api python -m alembic upgrade head
```

## Quick Diagnostic Commands

```bash
# Check all container statuses
docker ps -a

# Check API server logs
docker logs tradeagent-api --tail 100

# Check database logs
docker logs tradeagent-db --tail 50

# Test database connection
docker exec -e PGPASSWORD=changeme tradeagent-db psql -U trader -d tradeagent -c "SELECT 1;"

# Check network
docker network inspect docker_tradeagent-network

# Check environment variables
docker exec tradeagent-api env | grep -E "DB_URL|POSTGRES"
```
