# Production Rollback Guide

Complete guide for rolling back to a previous version of the application in production.

---

## 🚨 Quick Rollback (Git-Based)

**Use this when:** You need to revert to a previous git commit/version.

### Step 1: Identify Previous Version

```bash
# View recent commits
cd ~/modular_trade_agent
git log --oneline -10

# Or view tags (if you use version tags)
git tag -l
```

### Step 2: Backup Current State (Optional but Recommended)

```bash
# Backup database before rollback
docker exec tradeagent-api cp /app/data/app.db /app/data/app.db.backup.$(date +%Y%m%d_%H%M%S) || true

# Or backup entire data volume
docker run --rm -v modular_trade_agent_trading_data:/data -v $(pwd)/backups:/backup \
  alpine tar czf /backup/data-backup-$(date +%Y%m%d_%H%M%S).tar.gz -C /data .
```

### Step 3: Rollback Code

```bash
# Option A: Rollback to specific commit
git checkout <commit-hash>

# Option B: Rollback to previous commit
git checkout HEAD~1

# Option C: Rollback to specific tag
git checkout <tag-name>

# Option D: Rollback to specific branch
git checkout <branch-name>
```

### Step 4: Rebuild and Deploy

```bash
cd docker
docker-compose -f docker-compose.yml -f docker-compose.prod.yml stop
docker rm -f tradeagent-api tradeagent-web 2>/dev/null || true
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Step 5: Verify Rollback

```bash
# Check containers are running
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps

# Check logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail=50

# Test API health
curl http://localhost:8000/health
```

---

## 🏷️ Docker Image Tagging Strategy (Recommended)

**Use this when:** You want to tag images for easy rollback without git checkout.

### Before Deployment: Tag Current Images

```bash
# Tag current images before updating
docker tag $(docker images -q modular_trade_agent-api-server) tradeagent-api:previous
docker tag $(docker images -q modular_trade_agent-web-frontend) tradeagent-web:previous

# Or use version tags
docker tag $(docker images -q modular_trade_agent-api-server) tradeagent-api:v1.2.3
docker tag $(docker images -q modular_trade_agent-web-frontend) tradeagent-web:v1.2.3
```

### Rollback Using Tagged Images

```bash
cd docker

# Stop current containers
docker-compose -f docker-compose.yml -f docker-compose.prod.yml stop
docker rm -f tradeagent-api tradeagent-web 2>/dev/null || true

# Create temporary compose file with tagged images
cat > docker-compose.rollback.yml <<EOF
services:
  api-server:
    image: tradeagent-api:previous
  web-frontend:
    image: tradeagent-web:previous
EOF

# Start with previous images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.rollback.yml up -d

# Cleanup
rm docker-compose.rollback.yml
```

---

## 💾 Database Rollback

**Use this when:** You need to rollback database changes (migrations).

### Step 1: Check Migration History

```bash
# View migration history
docker exec tradeagent-api alembic history

# View current version
docker exec tradeagent-api alembic current
```

### Step 2: Rollback Database Migration

```bash
# Rollback one migration
docker exec tradeagent-api alembic downgrade -1

# Rollback to specific revision
docker exec tradeagent-api alembic downgrade <revision-hash>

# Rollback to base (⚠️ DANGEROUS - removes all migrations)
docker exec tradeagent-api alembic downgrade base
```

### Step 3: Restore Database from Backup

```bash
# If you have a database backup file
docker exec -i tradeagent-api cp /backup/app.db.backup.20250101_120000 /app/data/app.db

# Or restore from volume backup
docker run --rm -v modular_trade_agent_trading_data:/data -v $(pwd)/backups:/backup \
  alpine sh -c "cd /data && rm -f app.db && tar xzf /backup/data-backup-20250101_120000.tar.gz"
```

---

## 🔄 Complete Rollback Procedure

**Use this when:** You need to rollback everything (code + database).

```bash
#!/bin/bash
# Complete rollback script

set -e

echo "🚨 Starting complete rollback..."

# 1. Backup current state
echo "📦 Backing up current state..."
docker exec tradeagent-api cp /app/data/app.db /app/data/app.db.backup.$(date +%Y%m%d_%H%M%S) || true

# 2. Stop containers
echo "🛑 Stopping containers..."
cd ~/modular_trade_agent/docker
docker-compose -f docker-compose.yml -f docker-compose.prod.yml stop

# 3. Rollback code (replace with your commit/tag)
echo "📝 Rolling back code..."
cd ~/modular_trade_agent
PREVIOUS_COMMIT=$(git log --oneline -2 | tail -1 | cut -d' ' -f1)
echo "Rolling back to: $PREVIOUS_COMMIT"
git checkout $PREVIOUS_COMMIT

# 4. Remove containers
echo "🗑️  Removing containers..."
docker rm -f tradeagent-api tradeagent-web 2>/dev/null || true

# 5. Rebuild and start
echo "🔨 Rebuilding and starting..."
cd docker
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 6. Wait for services
echo "⏳ Waiting for services to start..."
sleep 10

# 7. Verify
echo "✅ Verifying rollback..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -f http://localhost:8000/health || echo "⚠️  Health check failed"

echo "✅ Rollback complete!"
```

---

## 📋 Rollback Checklist

Before rolling back:

- [ ] Identify the target version (commit/tag/image)
- [ ] Backup current database/data
- [ ] Note current migration version
- [ ] Check if rollback requires database migration rollback
- [ ] Verify you have access to previous version
- [ ] Plan downtime window (if needed)

During rollback:

- [ ] Stop containers gracefully
- [ ] Backup current state
- [ ] Rollback code/images
- [ ] Rollback database (if needed)
- [ ] Rebuild containers
- [ ] Start services
- [ ] Verify health checks

After rollback:

- [ ] Verify application is working
- [ ] Check logs for errors
- [ ] Test critical functionality
- [ ] Monitor for stability
- [ ] Document rollback reason

---

## 🎯 Rollback Scenarios

### Scenario 1: Code Bug (No DB Changes)

```bash
# Quick rollback - just revert code
cd ~/modular_trade_agent
git checkout <previous-commit>
cd docker
docker-compose -f docker-compose.yml -f docker-compose.prod.yml stop
docker rm -f tradeagent-api tradeagent-web 2>/dev/null || true
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Scenario 2: Database Migration Issue

```bash
# Rollback migration first, then code if needed
docker exec tradeagent-api alembic downgrade -1
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart api-server
```

### Scenario 3: Data Corruption

```bash
# Restore from backup
docker stop tradeagent-api
docker run --rm -v modular_trade_agent_trading_data:/data -v $(pwd)/backups:/backup \
  alpine sh -c "cd /data && rm -f app.db && tar xzf /backup/data-backup-LATEST.tar.gz"
docker start tradeagent-api
```

### Scenario 4: Complete System Rollback

```bash
# Use the complete rollback procedure above
# Includes: code + database + containers
```

---

## ⚠️ Important Notes

1. **Data Volumes**: Production uses named volumes (`trading_data`, `trading_logs`, `paper_trading_data`). These persist across container recreation, so your data is safe unless you explicitly remove volumes.

2. **Database Migrations**: If you rollback code that includes database migrations, you may need to rollback the migrations too. Check `alembic history` before and after.

3. **Configuration Changes**: If `.env` or config files changed, you may need to restore those too.

4. **Git State**: After rollback, your git repository will be in a detached HEAD state. To continue development:
   ```bash
   git checkout main  # or your branch
   git pull origin main
   ```

5. **Image Cleanup**: Old images take up space. Clean up periodically:
   ```bash
   docker image prune -a
   ```

---

## 🔍 Troubleshooting Rollback

### Containers Won't Start After Rollback

```bash
# Check logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs

# Check if volumes are accessible
docker volume inspect modular_trade_agent_trading_data

# Try rebuilding without cache
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache
```

### Database Migration Conflicts

```bash
# Check current migration state
docker exec tradeagent-api alembic current

# Force migration to match code
docker exec tradeagent-api alembic upgrade head
```

### Port Conflicts

```bash
# Check what's using the ports
netstat -tulpn | grep -E ':(8000|5173)'

# Stop conflicting services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
```

---

## 📚 Related Documentation

- [Deployment Guide](README.md)
- [Troubleshooting](DEPLOYMENT_TROUBLESHOOTING.md)
- [Container Config Fix](FIX_CONTAINER_CONFIG_ERROR.md)
