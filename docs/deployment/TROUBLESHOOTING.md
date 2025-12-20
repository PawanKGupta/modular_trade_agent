# Docker Deployment Troubleshooting Guide

> **Common Troubleshooting Guide** - This guide covers common issues and solutions for Docker-based deployments across all platforms.
> For platform-specific issues, see [Platform Deployment Guides](platforms/).
> For cloud provider specific issues, see [Cloud Deployment Guides](cloud/).

This comprehensive guide covers common issues, edge cases, and solutions for Docker-based deployments.

---

## 🔴 Critical Issues

### Issue: Docker Permission Denied

**Error:**
```
Got permission denied while trying to connect to the Docker daemon socket
```

**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Apply group changes (logout/login or use newgrp)
newgrp docker

# Verify membership
groups | grep docker

# Test access
docker ps

# If docker group doesn't exist:
sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker
```

**For Docker Deployment:**
```bash
# If still having issues, restart Docker daemon
sudo systemctl restart docker

# Verify Docker is running
sudo systemctl status docker
```

---

### Issue: Docker Compose Not Found

**Error:**
```
docker-compose: command not found
```

**Solution:**
```bash
# Check if Docker Compose is installed
docker-compose version

# If not installed, install Docker Compose v1
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Make it executable
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker-compose version

# Alternative: Install via pip (if curl method fails)
sudo apt-get update
sudo apt-get install -y python3-pip
sudo pip3 install docker-compose

# Verify installation
docker-compose --version
```

---

### Issue: ContainerConfig KeyError

**Error:**
```
KeyError: 'ContainerConfig'
```

**Solution:**
```bash
# Stop containers WITHOUT removing volumes (preserves data)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml stop

# Remove problematic containers (keeps volumes)
docker rm -f tradeagent-api tradeagent-web tradeagent-db 2>/dev/null || true

# Optional: Remove old images to force rebuild
docker rmi docker_api-server docker_web-frontend 2>/dev/null || true

# Rebuild and start fresh (volumes are preserved)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d --build
```

**⚠️ IMPORTANT:** Never use `docker-compose down` as it removes volumes and deletes your data!

---

### Issue: Database Connection Failed

**Error:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**For Docker Deployment:**
```bash
# Check if database container is running
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps tradeagent-db

# Check database logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs tradeagent-db

# Restart database container
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart tradeagent-db

# Check database health
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db pg_isready -U trader
```

---

### Issue: Port Already in Use

**Error:**
```
Error: bind: address already in use
```

**Solution:**
```bash
# Find process using port
sudo netstat -tlnp | grep -E ':(8000|5173|5432)'

# Or use lsof
sudo lsof -i :8000
sudo lsof -i :5173

# Kill process using port (replace PID with actual process ID)
sudo kill -9 <PID>

# For Docker: Stop containers first
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml down

# Then restart
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

---

## 🟡 Common Issues

### Issue: Chrome/Chromium Binary Not Found

**Error:**
```
ERROR — scrapping — Chrome/Chromium binary not found
```

**Solution:**
```bash
# Install Chromium and dependencies
sudo apt-get update

# Install Chromium (Ubuntu will auto-select correct package version)
sudo apt-get install -y chromium-browser chromium-chromedriver \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2

# Verify installation
chromium-browser --version || chromium --version

# For Docker: Chromium is included in the image, but if issues occur:
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart api-server
```

---

### Issue: Failed to Load ML Model

**Error:**
```
WARNING — ml_verdict_service — ⚠️ Failed to load ML model: 118
```

**Solution:**
```bash
cd /path/to/modular_trade_agent

# Install Git LFS if not already installed
sudo apt install -y git-lfs
git lfs install

# Pull ML model files from Git LFS
git lfs pull

# Verify model file exists
ls -la models/verdict_model_random_forest.pkl

# If still missing:
# 1. Check you're on the correct branch
git branch
git checkout main  # or your branch name

# 2. Pull again
git lfs pull

# 3. Or copy manually from local machine:
#    scp models/verdict_model_random_forest.pkl user@SERVER_IP:~/modular_trade_agent/models/

# For Docker: Rebuild API container to include model files
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml build api-server
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d api-server
```

---

### Issue: Services Not Starting

**For Docker Deployment:**
```bash
# Check service status
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps

# View logs for all services
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f

# View logs for specific service
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f api-server
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f web-frontend
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f tradeagent-db

# Restart specific service
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart api-server

# Rebuild and restart
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d --build api-server
```

---

### Issue: Database Migration Errors

**Error:**
```
alembic.util.exc.CommandError: Can't locate revision identified by 'xxxxx'
```

**Solution:**
```bash
cd /path/to/modular_trade_agent

# For Docker:
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec api-server alembic current
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec api-server alembic history
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec api-server alembic upgrade head

# If migration is stuck, check database state
# For PostgreSQL:
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db psql -U trader -d tradeagent -c "SELECT * FROM alembic_version;"

# For SQLite:
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec api-server sqlite3 data/app.db "SELECT * FROM alembic_version;"
```

---

### Issue: Web UI Not Accessible

**Symptoms:**
- Can't access `http://localhost:5173` or `http://YOUR_IP:5173`
- Connection timeout
- 404 error

**Solution:**
```bash
# 1. Check if service is running
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps web-frontend

# 2. Check if port is listening
sudo netstat -tlnp | grep 5173

# 3. Check service logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs web-frontend

# 4. Test from server itself
curl http://localhost:5173

# 5. Check if frontend build succeeded
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs web-frontend | grep -i error

# 6. Check firewall rules (if accessing from remote)
# Ensure port 5173 is open in firewall
```

---

### Issue: API Health Check Fails

**Error:**
```
curl http://localhost:8000/health
# Returns error or timeout
```

**Solution:**
```bash
# 1. Check if API service is running
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps api-server

# 2. Check API logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server -n 100

# 3. Check if port is listening
sudo netstat -tlnp | grep 8000

# 4. Test from server
curl http://localhost:8000/health

# 5. Check database connection (common cause)
# See "Database Connection Failed" section above

# 6. Restart API service
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart api-server
```

---

### Issue: Admin User Not Created

**Symptoms:**
- Can't login with admin credentials
- "Invalid credentials" error

**Solution:**
```bash
# 1. Check if admin user was created (check logs)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep -i admin

# 2. Check .env file has admin credentials
cat .env | grep ADMIN

# 3. Verify database has users table
# For PostgreSQL:
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db psql -U trader -d tradeagent -c "SELECT email, role FROM users;"

# For SQLite:
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec api-server sqlite3 data/app.db "SELECT email, role FROM users;"

# 4. If no users exist, restart API server (it will create admin on startup)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart api-server

# 5. Check logs for admin creation
# Should see: "[Startup] Creating admin user admin@example.com"
```

---

## 🔵 Resource & Performance Issues

### Issue: Out of Memory

**Symptoms:**
- Services crash
- "Killed" processes
- Slow performance

**Solution:**
```bash
# Check memory usage
free -h

# Check which processes use most memory
top
# Or:
htop

# For Docker: Check container resource usage
docker stats

# Solutions:
# 1. Increase Docker memory allocation (Docker Desktop → Settings → Resources)
# 2. Reduce number of stocks analyzed
# 3. Increase swap space (temporary fix)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

### Issue: Out of Disk Space

**Solution:**
```bash
# Check disk usage
df -h

# Find large files/directories
du -sh /path/to/modular_trade_agent/* | sort -h

# Clean Docker (if using Docker)
docker system prune -a --volumes  # ⚠️ Removes unused images/volumes

# Clean logs
sudo journalctl --vacuum-time=7d  # Keep last 7 days

# Clean apt cache
sudo apt-get clean
sudo apt-get autoclean
```

---

## 🟣 Build & Installation Issues

### Issue: Docker Build Fails

**Error:**
```
ERROR: failed to solve: process "/bin/sh -c ..." did not complete successfully
```

**Solution:**
```bash
# Build without cache
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml build --no-cache

# Build specific service
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml build --no-cache api-server

# Check build logs for specific errors
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml build api-server 2>&1 | tee build.log

# Common fixes:
# 1. Ensure Git LFS is installed and models are pulled
# 2. Check internet connection (for package downloads)
# 3. Increase Docker build memory if needed
```

---

### Issue: Git LFS Files Not Pulled

**Symptoms:**
- ML model files missing
- Large files show as pointers

**Solution:**
```bash
# Install Git LFS
sudo apt install -y git-lfs
git lfs install

# Pull LFS files
git lfs pull

# Verify files are actual files, not pointers
ls -lh models/verdict_model_random_forest.pkl
# Should show actual file size (not 130 bytes)

# If still pointers:
git lfs fetch
git lfs checkout

# Check Git LFS status
git lfs ls-files
```

---

## 🟠 Edge Cases & Advanced Issues

### Issue: Timezone Issues

**Symptoms:**
- Trading times incorrect
- Orders placed at wrong time

**Solution:**
```bash
# Check current timezone
timedatectl

# Set timezone to Asia/Kolkata
sudo timedatectl set-timezone Asia/Kolkata

# Verify
date

# For Docker: Timezone is set in .env file (TZ=Asia/Kolkata)
# Restart services after timezone change
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart
```

---

### Issue: Encryption Key Issues

**Error:**
```
cryptography.fernet.InvalidToken
```

**Solution:**
```bash
# Check .env file has ENCRYPTION_KEY
cat .env | grep ENCRYPTION_KEY

# Generate new encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Update .env file with new key
# ⚠️ WARNING: This will invalidate existing encrypted credentials!
# You'll need to re-enter broker credentials via Web UI

# Restart services
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml restart api-server
```

---

### Issue: Service Auto-Restart Loop

**Symptoms:**
- Service keeps restarting
- Logs show repeated errors

**Solution:**
```bash
# Check service status and logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server --tail=100

# Common causes:
# 1. Database connection failure → Fix database (see above)
# 2. Missing environment variables → Check .env file
# 3. Port conflict → Fix port issue (see above)
# 4. Missing files → Check Git LFS, model files

# Temporarily disable auto-restart to debug:
# Remove restart: unless-stopped from docker-compose.yml temporarily
```

---

## 📋 Docker Logs Debugging Commands

### Basic Log Commands

```bash
# View logs for all services (last 100 lines)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=100

# View logs for specific service
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=100 api-server
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=100 web-frontend
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=100 tradeagent-db

# Follow logs in real-time (all services)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f

# Follow logs for specific service
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f api-server
```

### Filtering and Searching Logs

```bash
# View logs with timestamps
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -t

# View logs since specific time
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --since 30m
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --since 1h

# Filter logs by service and search for specific text
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep -i error
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep -i "database"

# View only errors
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep -i "error\|exception\|failed\|traceback"

# View logs with context (lines before and after match)
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep -A 5 -B 5 "error"
```

### Service-Specific Log Debugging

```bash
# API Server Logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep -i "startup\|initialization\|migration"
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep -i "database\|postgres\|sqlite\|connection"
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep -i "login\|auth\|jwt\|token"
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep -i "trading\|order\|signal\|analysis"

# Web Frontend Logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs web-frontend | grep -i "build\|compile\|error"
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs web-frontend | grep -i "server\|nginx\|vite"

# Database Logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs tradeagent-db | grep -i "connection\|authentication"
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs tradeagent-db | grep -i "error\|fatal\|panic"
```

### User-Specific Log Debugging

**Filter and view logs for specific users (useful for multi-user deployments):**

```bash
# Find user ID from email
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec api-server python -c "
from src.infrastructure.db.session import SessionLocal
from src.infrastructure.db.models import Users
db = SessionLocal()
user = db.query(Users).filter(Users.email == 'user@example.com').first()
if user:
    print(f'User ID: {user.id}, Email: {user.email}, Name: {user.name}')
db.close()
"

# View logs for specific user ID
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep "user_id.*123"
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep "uid.*123"

# View logs for specific user email
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep "user@example.com"

# View user authentication logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep -iE "login|signup|auth.*user@example.com"

# View user trading activity logs
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep -E "user_id.*123|uid.*123" | grep -iE "trading|order|signal|analysis"

# View user-specific errors
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs api-server | grep -E "user_id.*123|uid.*123" | grep -iE "error|exception|failed|traceback"

# Follow user-specific logs in real-time
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f api-server | grep --line-buffered -E "user_id.*123|uid.*123"
```

---

## 📋 Quick Diagnostic Commands

**Run these to diagnose common issues:**

```bash
# System health
free -h                    # Memory
df -h                      # Disk space
uptime                     # System load

# Service status
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml ps
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs --tail=50

# Network
sudo netstat -tlnp | grep -E ':(8000|5173|5432)'
curl http://localhost:8000/health
curl http://localhost:5173

# Database
# PostgreSQL:
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec tradeagent-db psql -U trader -d tradeagent -c "SELECT COUNT(*) FROM users;"

# SQLite:
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec api-server sqlite3 data/app.db "SELECT COUNT(*) FROM users;"

# Files
ls -la .env
ls -la models/
ls -la data/
```

---

## 🖥️ Platform-Specific Issues

### Windows-Specific Issues

#### Issue: WSL2 Backend Not Working

**Error:**
```
WSL 2 installation is incomplete
```

**Solution:**
```powershell
# Update WSL2
wsl --update

# Set default version to WSL2
wsl --set-default-version 2

# Verify WSL2 status
wsl --list --verbose

# Restart Docker Desktop
```

#### Issue: Windows Firewall Blocking Docker

**Symptoms:**
- Can't access services from other devices on network
- Connection timeout

**Solution:**
```powershell
# Allow Docker Desktop through Windows Firewall
# 1. Open Windows Defender Firewall
# 2. Click "Allow an app or feature through Windows Defender Firewall"
# 3. Find "Docker Desktop" and enable both Private and Public
# 4. Or use PowerShell:
New-NetFirewallRule -DisplayName "Docker Desktop" -Direction Inbound -Program "C:\Program Files\Docker\Docker\Docker Desktop.exe" -Action Allow
```

#### Issue: PowerShell Execution Policy

**Error:**
```
cannot be loaded because running scripts is disabled on this system
```

**Solution:**
```powershell
# Run PowerShell as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Verify
Get-ExecutionPolicy
```

#### Issue: Port Already in Use (Windows)

**Solution:**
```powershell
# Find process using port
netstat -ano | findstr :5173
netstat -ano | findstr :8000

# Kill process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

---

### macOS-Specific Issues

#### Issue: Docker Desktop Permission Denied

**Error:**
```
Permission denied: /var/run/docker.sock
```

**Solution:**
```bash
# Ensure Docker Desktop has Full Disk Access
# 1. System Preferences → Security & Privacy → Privacy → Full Disk Access
# 2. Add Docker Desktop
# 3. Restart Docker Desktop

# Verify Docker is accessible
docker ps
```

#### Issue: Apple Silicon (M1/M2/M3) Compatibility

**Error:**
```
exec format error
```

**Solution:**
```bash
# Most images support multi-architecture automatically
# If issues occur, explicitly specify platform:
docker-compose -f docker/docker-compose.yml -f docker/docker-compose.yml build --platform linux/amd64

# Or in docker-compose.yml, add platform specification:
# platform: linux/amd64
```

#### Issue: macOS Firewall Blocking Docker

**Solution:**
```bash
# 1. System Preferences → Security & Privacy → Firewall
# 2. Click "Firewall Options"
# 3. Add Docker Desktop to allowed applications
# 4. Ensure "Block all incoming connections" is NOT checked
```

#### Issue: Port Already in Use (macOS)

**Solution:**
```bash
# Find process using port
lsof -i :5173
lsof -i :8000

# Kill process (replace PID with actual process ID)
kill -9 <PID>
```

#### Issue: File Sharing Not Working

**Error:**
```
Cannot access project files
```

**Solution:**
```bash
# 1. Docker Desktop → Settings → Resources → File Sharing
# 2. Add project directory if not listed
# 3. Ensure project is not in system-protected folders
# 4. Restart Docker Desktop
```

---

### Linux-Specific Issues

#### Issue: SELinux Blocking Docker (CentOS/RHEL)

**Error:**
```
SELinux is preventing docker from access
```

**Solution:**
```bash
# Temporary fix (permissive mode)
sudo setenforce 0

# Permanent fix (configure SELinux for Docker)
sudo setsebool -P container_manage_cgroup on

# Verify SELinux status
getenforce
```

#### Issue: Firewall Blocking Ports (UFW - Ubuntu/Debian)

**Solution:**
```bash
# Allow ports through UFW
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 5173/tcp  # Web UI
sudo ufw allow 8000/tcp  # API

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

#### Issue: Firewall Blocking Ports (firewalld - CentOS/RHEL)

**Solution:**
```bash
# Allow ports through firewalld
sudo firewall-cmd --permanent --add-port=22/tcp   # SSH
sudo firewall-cmd --permanent --add-port=5173/tcp # Web UI
sudo firewall-cmd --permanent --add-port=8000/tcp # API

# Reload firewall
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports
```

#### Issue: Docker Service Not Starting (systemd)

**Solution:**
```bash
# Start Docker service
sudo systemctl start docker

# Enable on boot
sudo systemctl enable docker

# Check status
sudo systemctl status docker

# View logs if failed
sudo journalctl -u docker -n 50
```

---

## 🆘 Still Having Issues?

1. **Check logs thoroughly:**
   - `docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f`

2. **Verify all prerequisites:**
   - Firewall rules configured
   - Ports not in use
   - Sufficient resources (RAM, disk)

3. **Review deployment steps:**
   - Ensure all steps completed successfully
   - Check for any error messages during deployment

4. **Check related documentation:**
   - [Platform Deployment Guides](platforms/) - Platform-specific deployment guides
   - [Health Check Guide](HEALTH_CHECK.md)
   - [Platform Deployment Guides](platforms/) - Platform-specific deployment guides
   - [Cloud Deployment Guides](cloud/) - Cloud provider specific guides

---

## 🔗 Related Documentation

- [Deployment Guide](DEPLOYMENT.md) - Deployment index and routing guide
- [Platform Deployment Guides](platforms/) - Platform-specific Docker deployment guides
- [Health Check Guide](HEALTH_CHECK.md) - Health monitoring
- [Backup & Restore Guide](BACKUP_RESTORE_UNINSTALL_GUIDE.md) - Data backup procedures
