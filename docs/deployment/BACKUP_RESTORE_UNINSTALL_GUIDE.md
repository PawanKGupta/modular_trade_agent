# Backup, Restore & Uninstallation Guide

> **Docker Deployment Guide** - This guide covers backup, restore, and uninstallation procedures for Docker-based deployments.
> For platform-specific deployment instructions, see [Platform Deployment Guides](platforms/).

## Overview

This guide covers backup, restore, and uninstallation procedures for the Modular Trade Agent when deployed using Docker.

---

## 📦 Backup Procedures

### Database Backup (PostgreSQL)

All application data, including user accounts, trading history, orders, and encrypted broker credentials, is stored in the PostgreSQL database.

#### Manual Backup

```bash
# Backup PostgreSQL database
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db pg_dump -U trader tradeagent > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup with custom format (smaller, faster restore)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db pg_dump -U trader -F c tradeagent > backup_$(date +%Y%m%d_%H%M%S).dump
```

#### Automated Backup Script

Create a backup script:

```bash
#!/bin/bash
# backup.sh - Automated database backup

BACKUP_DIR="./backups"
mkdir -p $BACKUP_DIR

# Create timestamped backup
BACKUP_FILE="$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql"

docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec -T tradeagent-db pg_dump -U trader tradeagent > $BACKUP_FILE

# Compress backup
gzip $BACKUP_FILE

# Keep only last 7 days of backups
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE.gz"
```

**Windows PowerShell version:**

```powershell
# backup.ps1 - Automated database backup

$BackupDir = ".\backups"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$BackupFile = "$BackupDir\backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"

docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec -T tradeagent-db pg_dump -U trader tradeagent | Out-File -FilePath $BackupFile -Encoding utf8

# Compress backup (requires 7-Zip or similar)
# Compress-Archive -Path $BackupFile -DestinationPath "$BackupFile.zip"

# Keep only last 7 days
Get-ChildItem $BackupDir -Filter "backup_*.sql" | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item

Write-Host "Backup completed: $BackupFile"
```

#### Scheduled Backups (Linux/macOS)

Add to crontab:

```bash
# Daily backup at 2 AM
0 2 * * * cd /path/to/modular_trade_agent && ./backup.sh
```

#### Scheduled Backups (Windows)

Use Task Scheduler:

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., daily at 2 AM)
4. Action: Start a program
5. Program: `powershell.exe`
6. Arguments: `-File "C:\path\to\modular_trade_agent\backup.ps1"`

### Docker Volume Backup

If you want to backup the entire Docker volume (including database):

```bash
# Stop services (optional, for consistent backup)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml stop

# Backup volume
docker run --rm -v modular_trade_agent_postgres_data:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres_data_backup_$(date +%Y%m%d_%H%M%S).tar.gz /data

# Start services
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml start
```

### Configuration Backup

Backup `.env` file and other configuration:

```bash
# Backup .env file
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# Backup entire configuration
tar czf config_backup_$(date +%Y%m%d_%H%M%S).tar.gz .env docker/
```

---

## 🔄 Restore Procedures

### Database Restore

#### From SQL Dump

```bash
# Restore from SQL dump
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec -T tradeagent-db psql -U trader tradeagent < backup_20250101_120000.sql
```

#### From Custom Format Dump

```bash
# Restore from custom format dump
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec -T tradeagent-db pg_restore -U trader -d tradeagent backup_20250101_120000.dump
```

#### Restore Process

1. **Stop services** (optional, for clean restore):
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml stop
   ```

2. **Drop existing database** (if needed):
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db psql -U trader -c "DROP DATABASE IF EXISTS tradeagent;"
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db psql -U trader -c "CREATE DATABASE tradeagent;"
   ```

3. **Restore backup**:
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec -T tradeagent-db psql -U trader tradeagent < backup_20250101_120000.sql
   ```

4. **Start services**:
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml start
   ```

### Docker Volume Restore

```bash
# Stop services
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml down

# Remove existing volume (WARNING: This deletes current data!)
docker volume rm modular_trade_agent_postgres_data

# Restore volume
docker run --rm -v modular_trade_agent_postgres_data:/data -v $(pwd):/backup ubuntu tar xzf /backup/postgres_data_backup_20250101_120000.tar.gz -C /

# Start services
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

### Configuration Restore

```bash
# Restore .env file
cp .env.backup.20250101_120000 .env

# Restore entire configuration
tar xzf config_backup_20250101_120000.tar.gz
```

---

## 🗑️ Uninstallation

### Complete Uninstallation (Removes All Data)

**⚠️ WARNING:** This removes all containers, volumes, and data. This cannot be undone!

```bash
# Stop and remove all containers and volumes
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml down -v

# Remove images (optional)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml down --rmi all

# Remove Docker volumes (if any remain)
docker volume ls | grep modular_trade_agent
docker volume rm modular_trade_agent_postgres_data
```

### Partial Uninstallation (Keeps Data)

**Preserves database and volumes:**

```bash
# Stop containers only (keeps volumes)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml stop

# Remove containers only (keeps volumes)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml down
```

### Clean Uninstallation Checklist

- [ ] Backup database (see Backup Procedures above)
- [ ] Backup `.env` file
- [ ] Stop all services
- [ ] Remove containers
- [ ] Remove volumes (if complete removal)
- [ ] Remove images (optional)
- [ ] Remove project directory (optional)
- [ ] Verify backup before deletion

---

## 📋 Best Practices

### Backup Strategy

1. **Regular Backups:**
   - Daily: After trading session
   - Weekly: Archive to external storage
   - Monthly: Long-term storage

2. **Backup Retention:**
   - Keep last 7 daily backups
   - Keep last 4 weekly backups
   - Keep monthly backups indefinitely

3. **Before Major Changes:**
   - Always backup before updates
   - Test restore procedure periodically
   - Keep multiple backup versions

### Backup Verification

```bash
# Verify backup file exists and is not empty
ls -lh backup_*.sql

# Test restore on a test database
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db psql -U trader -c "CREATE DATABASE tradeagent_test;"
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec -T tradeagent-db psql -U trader tradeagent_test < backup_20250101_120000.sql
```

### Disaster Recovery

1. **Complete System Failure:**
   - Restore from latest database backup
   - Restore `.env` configuration
   - Rebuild Docker containers
   - Verify all services running

2. **Data Corruption:**
   - Stop services
   - Restore from backup
   - Verify data integrity
   - Restart services

3. **Configuration Loss:**
   - Restore `.env` file
   - Restart services
   - Verify Web UI accessible

---

## 🔗 Related Documentation

- [Deployment Guide](DEPLOYMENT.md) - Deployment index and routing guide
- [Platform Deployment Guides](platforms/) - Platform-specific Docker deployment guides
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common troubleshooting issues
- [Health Check Guide](HEALTH_CHECK.md) - Health monitoring

---

## 🆘 Support

For issues with backup, restore, or uninstallation:

1. Check backup file exists and is not corrupted
2. Verify Docker services are running
3. Check Docker logs for errors
4. Review [Troubleshooting Guide](TROUBLESHOOTING.md)
5. Ensure sufficient disk space for backups

---

**Last Updated:** 2025-01-XX
**Version:** 26.1.0
