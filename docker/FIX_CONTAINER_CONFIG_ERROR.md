# Fixing ContainerConfig KeyError

If you see this error:
```
KeyError: 'ContainerConfig'
```

This is a known bug in Docker Compose v1.29.2 when recreating containers.

## ⚠️ SAFE Fix (Preserves Data)

**IMPORTANT:** Do NOT use `docker-compose down` as it removes volumes and deletes your data!

Run these commands on your Ubuntu server:

```bash
cd ~/modular_trade_agent/docker

# Stop containers WITHOUT removing volumes
docker-compose -f docker-compose.yml -f docker-compose.prod.yml stop

# Remove the problematic containers (keeps volumes)
docker rm -f tradeagent-api tradeagent-web 2>/dev/null || true

# Optional: Remove old images to force rebuild
docker rmi docker_api-server docker_web-frontend 2>/dev/null || true

# Rebuild and start fresh (volumes are preserved)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Alternative: Fix Only One Container

If you want to keep the API container running:

```bash
# Stop and remove just the web container
docker stop tradeagent-web
docker rm -f tradeagent-web

# Then recreate it
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d web-frontend
```

## ⚠️ Data Recovery (If You Already Ran `down`)

If you already ran `docker-compose down` and lost your data:

1. **Check if volumes still exist:**
   ```bash
   docker volume ls | grep trading
   ```

2. **If volumes exist, you can restore by:**
   ```bash
   # Start containers - they will reconnect to existing volumes
   docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```

3. **If volumes are gone, restore from backup:**
   ```bash
   # If you have backups in ~/backups/
   cd ~/modular_trade_agent
   cp ~/backups/app.db data/app.db
   # Then start containers
   cd docker
   docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```

## Root Cause

The error occurs when Docker Compose tries to inspect an existing container's image metadata and encounters corrupted or missing data. Removing and recreating fixes it.

## Prevention

To avoid this error and data loss:

1. **NEVER use `docker-compose down`** - it removes volumes and deletes data
2. **Use `docker-compose stop`** instead - safely stops containers without removing volumes
3. **For updates:** Use `docker-compose up -d --build` - recreates containers but keeps volumes
4. **Backup regularly:** Set up automated backups of your data directory
5. **Named volumes are configured** - they persist even when containers are removed (unless you use `down -v`)
