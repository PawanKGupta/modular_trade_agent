# Fixing ContainerConfig KeyError

If you see this error:
```
KeyError: 'ContainerConfig'
```

This is a known bug in Docker Compose v1.29.2 when recreating containers.

## ⚠️ SAFE Fix (Preserves Data)

**IMPORTANT:** Do NOT use `docker compose down` as it removes volumes and deletes your data!

Run these commands on your Ubuntu server:

```bash
cd ~/rebound   # or wherever your compose files live

# Stop containers WITHOUT removing volumes
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop

# Remove the problematic containers (keeps volumes)
docker rm -f tradeagent-api tradeagent-web 2>/dev/null || true

# Optional: Remove old images so a fresh pull is used
docker rmi ghcr.io/pawankgupta/modular_trade_agent/api ghcr.io/pawankgupta/modular_trade_agent/web 2>/dev/null || true

# Pull latest image and start fresh (volumes are preserved)
export APP_VERSION=v26.2.3.1
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Alternative: Fix Only One Container

If you want to keep the API container running:

```bash
# Stop and remove just the web container
docker stop tradeagent-web
docker rm -f tradeagent-web

# Then recreate it
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d web-frontend
```

## ⚠️ Data Recovery (If You Already Ran `down`)

If you already ran `docker compose down` and lost your data:

1. **Check if volumes still exist:**
   ```bash
   docker volume ls | grep trading
   ```

2. **If volumes exist, you can restore by:**
   ```bash
   # Pull image and start — containers reconnect to existing volumes
   export APP_VERSION=v26.2.3.1
   docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

3. **If volumes are gone, restore from backup:**
   ```bash
   # Restore Postgres dump (see docs/deployment/BACKUP_RESTORE_UNINSTALL_GUIDE.md)
   # Then start containers
   export APP_VERSION=v26.2.3.1
   docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

## Root Cause

The error occurs when Docker Compose tries to inspect an existing container's image metadata and encounters corrupted or missing data. Removing and recreating fixes it.

## Prevention

To avoid this error and data loss:

1. **NEVER use `docker compose down`** without `-v` — `down` alone keeps volumes, but be cautious
2. **Use `docker compose stop`** to safely stop containers without touching volumes
3. **For updates:** `APP_VERSION=vX docker compose pull && docker compose up -d` — pulls new image, keeps volumes
4. **Backup regularly:** See [Backup & Restore Guide](../docs/deployment/BACKUP_RESTORE_UNINSTALL_GUIDE.md)
5. **Named volumes are configured** - they persist even when containers are removed (only lost with `down -v`)
