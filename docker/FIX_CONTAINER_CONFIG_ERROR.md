# Fixing ContainerConfig KeyError

If you see this error:
```
KeyError: 'ContainerConfig'
```

This is a known bug in Docker Compose v1.29.2 when recreating containers.

## Quick Fix

Run these commands on your Ubuntu server:

```bash
cd ~/modular_trade_agent/docker

# Stop and remove all containers
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down

# Remove the problematic container/image (if needed)
docker rm -f tradeagent-web 2>/dev/null || true
docker rmi docker_web-frontend 2>/dev/null || true

# Rebuild and start fresh
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Alternative: Force Remove Only Web Container

If you want to keep the API container running:

```bash
# Force remove just the web container
docker rm -f tradeagent-web

# Then recreate it
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d web-frontend
```

## Root Cause

The error occurs when Docker Compose tries to inspect an existing container's image metadata and encounters corrupted or missing data. Removing and recreating fixes it.

## Prevention

If this happens frequently, consider:
1. Always use `docker-compose down` before major changes
2. Rebuild images when configuration changes: `docker-compose up -d --build`
3. Use named volumes to persist data (already configured)
