# Health Check Guide

> **Docker Deployment Guide** - This guide covers health check procedures for Docker-based deployments.
> For platform-specific deployment instructions, see [Platform Deployment Guides](platforms/).

## Overview

This guide covers health check procedures for verifying that the Modular Trade Agent is properly deployed and functioning correctly when using Docker.

---

## 🏥 Health Check Methods

### Method 1: API Health Endpoint (Recommended)

The simplest way to check system health:

```bash
# Check API health
curl http://localhost:8000/health

# Expected response:
# {"status": "ok"}
```

**From browser:**
- Navigate to: http://localhost:8000/health
- Should display: `{"status": "ok"}`

### Method 2: Docker Service Status

Check if all Docker services are running:

```bash
# Check service status
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps

# Expected output:
# NAME                STATUS          PORTS
# api-server          Up 5 minutes    0.0.0.0:8000->8000/tcp
# web-frontend        Up 5 minutes    0.0.0.0:5173->5173/tcp
# tradeagent-db       Up 5 minutes    5432/tcp
```

### Method 3: Service Logs

Check logs for errors:

```bash
# View all service logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=50

# View specific service logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=50 api-server
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=50 web-frontend
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=50 tradeagent-db
```

---

## ✅ What Gets Checked

### 1. Docker Services

**Check:**
- All containers are running
- No containers are restarting repeatedly
- Ports are properly mapped

**Commands:**
```bash
# Service status
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps

# Check for restarting containers
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps | grep -i restart
```

### 2. API Server

**Check:**
- API server is responding
- Health endpoint returns OK
- Database connection is working

**Commands:**
```bash
# Health check
curl http://localhost:8000/health

# API docs
curl http://localhost:8000/docs

# Check API logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep -i error
```

### 3. Web Frontend

**Check:**
- Web UI is accessible
- Frontend is serving correctly

**Commands:**
```bash
# Check if port is listening
curl http://localhost:5173

# Check frontend logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs web-frontend | grep -i error
```

### 4. Database

**Check:**
- Database container is running
- Database is accepting connections
- Migrations are applied

**Commands:**
```bash
# Check database status
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db pg_isready -U trader

# Check database connection
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db psql -U trader -d tradeagent -c "SELECT version();"

# Check migrations
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec api-server alembic current
```

### 5. Configuration

**Check:**
- `.env` file exists
- Required environment variables are set
- Database connection string is correct

**Commands:**
```bash
# Check .env file exists
ls -la .env

# Check environment variables (without exposing secrets)
cat .env | grep -E "^[A-Z_]+=" | grep -v "PASSWORD\|SECRET\|KEY" | head -10
```

**Note:** Broker credentials are configured via Web UI (Settings → Broker Credentials), not in `.env` files.

### 6. Network Connectivity

**Check:**
- Ports are accessible
- No port conflicts

**Commands:**
```bash
# Check if ports are listening
# Linux/macOS:
netstat -tlnp | grep -E ':(8000|5173|5432)'
# Or:
lsof -i :8000
lsof -i :5173

# Windows:
netstat -ano | findstr :8000
netstat -ano | findstr :5173
```

### 7. Resource Usage

**Check:**
- Sufficient memory available
- Sufficient disk space
- CPU usage is reasonable

**Commands:**
```bash
# Docker resource usage
docker stats --no-stream

# System resources
# Linux:
free -h
df -h

# macOS:
vm_stat
df -h

# Windows:
# Use Task Manager or:
Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory
```

---

## 🔍 Comprehensive Health Check Script

Create a health check script:

```bash
#!/bin/bash
# health_check.sh - Comprehensive Docker health check

echo "=========================================="
echo "Modular Trade Agent - Health Check"
echo "=========================================="
echo ""

# Check Docker services
echo "1. Checking Docker services..."
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps
echo ""

# Check API health
echo "2. Checking API health..."
if curl -s http://localhost:8000/health | grep -q "ok"; then
    echo "✓ API health check: OK"
else
    echo "✗ API health check: FAILED"
fi
echo ""

# Check Web UI
echo "3. Checking Web UI..."
if curl -s http://localhost:5173 > /dev/null; then
    echo "✓ Web UI: Accessible"
else
    echo "✗ Web UI: Not accessible"
fi
echo ""

# Check database
echo "4. Checking database..."
if docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec -T tradeagent-db pg_isready -U trader > /dev/null 2>&1; then
    echo "✓ Database: Ready"
else
    echo "✗ Database: Not ready"
fi
echo ""

# Check logs for errors
echo "5. Checking for errors in logs..."
ERROR_COUNT=$(docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=100 | grep -i "error\|exception\|failed" | wc -l)
if [ $ERROR_COUNT -eq 0 ]; then
    echo "✓ No recent errors in logs"
else
    echo "⚠ Found $ERROR_COUNT potential errors in recent logs"
fi
echo ""

echo "=========================================="
echo "Health Check Complete"
echo "=========================================="
```

**Windows PowerShell version:**

```powershell
# health_check.ps1 - Comprehensive Docker health check

Write-Host "=========================================="
Write-Host "Modular Trade Agent - Health Check"
Write-Host "=========================================="
Write-Host ""

# Check Docker services
Write-Host "1. Checking Docker services..."
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps
Write-Host ""

# Check API health
Write-Host "2. Checking API health..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing
    if ($response.Content -match "ok") {
        Write-Host "✓ API health check: OK" -ForegroundColor Green
    } else {
        Write-Host "✗ API health check: FAILED" -ForegroundColor Red
    }
} catch {
    Write-Host "✗ API health check: FAILED" -ForegroundColor Red
}
Write-Host ""

# Check Web UI
Write-Host "3. Checking Web UI..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing
    Write-Host "✓ Web UI: Accessible" -ForegroundColor Green
} catch {
    Write-Host "✗ Web UI: Not accessible" -ForegroundColor Red
}
Write-Host ""

# Check database
Write-Host "4. Checking database..."
$dbCheck = docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec -T tradeagent-db pg_isready -U trader 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Database: Ready" -ForegroundColor Green
} else {
    Write-Host "✗ Database: Not ready" -ForegroundColor Red
}
Write-Host ""

Write-Host "=========================================="
Write-Host "Health Check Complete"
Write-Host "=========================================="
```

---

## 🚨 Common Issues and Solutions

### Issue: API Health Check Fails

**Symptoms:**
- `curl http://localhost:8000/health` returns error or timeout

**Solutions:**
1. Check if API container is running:
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps api-server
   ```

2. Check API logs:
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server
   ```

3. Restart API service:
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart api-server
   ```

### Issue: Web UI Not Accessible

**Symptoms:**
- Can't access http://localhost:5173

**Solutions:**
1. Check if frontend container is running:
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps web-frontend
   ```

2. Check frontend logs:
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs web-frontend
   ```

3. Restart frontend service:
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart web-frontend
   ```

### Issue: Database Not Ready

**Symptoms:**
- Database health check fails
- API can't connect to database

**Solutions:**
1. Check if database container is running:
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps tradeagent-db
   ```

2. Check database logs:
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs tradeagent-db
   ```

3. Restart database service:
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart tradeagent-db
   ```

### Issue: Services Restarting Repeatedly

**Symptoms:**
- Containers show "Restarting" status
- High restart count

**Solutions:**
1. Check logs for errors:
   ```bash
   docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=100
   ```

2. Check resource usage:
   ```bash
   docker stats
   ```

3. See [Troubleshooting Guide](TROUBLESHOOTING.md) for detailed solutions

---

## 📊 Automated Health Monitoring

### Scheduled Health Checks (Linux/macOS)

Add to crontab:

```bash
# Health check every hour
0 * * * * cd /path/to/modular_trade_agent && ./health_check.sh >> health_check.log 2>&1
```

### Scheduled Health Checks (Windows)

Use Task Scheduler:

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., hourly)
4. Action: Start a program
5. Program: `powershell.exe`
6. Arguments: `-File "C:\path\to\modular_trade_agent\health_check.ps1"`

---

## 🔗 Related Documentation

- [Deployment Guide](DEPLOYMENT.md) - Deployment index and routing guide
- [Platform Deployment Guides](platforms/) - Platform-specific Docker deployment guides
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common troubleshooting issues
- [Backup & Restore Guide](BACKUP_RESTORE_UNINSTALL_GUIDE.md) - Data backup procedures

---

## 💡 Best Practices

1. **Run health check after deployment**
   - Verify everything is set up correctly
   - Address any issues before starting trading services

2. **Run before troubleshooting**
   - Quickly identify problem areas
   - Get comprehensive status overview

3. **Include in monitoring**
   - Automated health checks
   - Alert on failures
   - Continuous monitoring

4. **Regular health checks**
   - Daily checks recommended
   - Before and after updates
   - After system changes

---

**Last Updated:** 2025-01-XX
**Version:** 26.1.0
