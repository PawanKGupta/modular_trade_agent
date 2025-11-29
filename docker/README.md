# Docker Setup Guide

Complete guide for running the Trading Agent with Docker.

## 🚀 Quick Start

### Windows (PowerShell)
```powershell
# From project root
.\docker\docker-quickstart.ps1
```

### Linux/Mac
```bash
# From project root
./docker/docker-quickstart.sh
```

### Manual Start
```bash
cd docker
docker-compose -f docker-compose.yml up -d
```

**Access:**
- Web UI: http://localhost:5173
- API: http://localhost:8000
- Health: http://localhost:8000/health

---

## 📋 Prerequisites

- Docker Desktop installed and running
- Git (to clone the repository)

---

## ⚙️ Configuration

### 1. Create `.env` File (Project Root)

Create `.env` in the project root with:

```bash
# Database
DB_URL=sqlite:///./data/app.db

# Timezone
TZ=Asia/Kolkata

# Admin User (auto-created on first deployment when DB is empty)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change_me
ADMIN_NAME=Admin User

# Optional: Encryption key for credential encryption
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# ENCRYPTION_KEY=your_base64_encoded_key
```

**Important:** Admin user is only created automatically when:
- Database is empty (0 users)
- `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set in `.env`

### 2. Credentials Management

**All credentials are stored in the database** (not in `.env` files):

1. Start Docker: `docker-compose -f docker-compose.yml up -d`
2. Access web UI: http://localhost:5173
3. Login with admin credentials
4. Go to **Settings**:
   - Configure **Broker credentials** (Kotak Neo)
   - Configure **Telegram settings**

**Note:** No `.env` file fallback for credentials - configure via web UI only.

---

## 🛠️ Common Commands

### Start Services
```bash
cd docker
docker-compose -f docker-compose.yml up -d
```

### Stop Services
```bash
docker-compose -f docker-compose.yml down
```

### View Logs
```bash
# All services
docker-compose -f docker-compose.yml logs -f

# Specific service
docker-compose -f docker-compose.yml logs -f api-server
docker-compose -f docker-compose.yml logs -f web-frontend
```

### Restart Service
```bash
docker-compose -f docker-compose.yml restart api-server
```

### Rebuild After Code Changes
```bash
docker-compose -f docker-compose.yml build api-server
docker-compose -f docker-compose.yml restart api-server
```

### Check Status
```bash
docker-compose -f docker-compose.yml ps
```

---

## 🔧 Development Mode (Windows)

For hot reload and live code editing:

```powershell
cd docker
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

**Features:**
- API server auto-reloads on code changes
- Web frontend uses Vite dev server (HMR)
- Source code mounted for live editing

---

## ☁️ Production Deployment (Oracle Ubuntu)

### Quick Deploy
```bash
# SSH into your Ubuntu server
ssh ubuntu@YOUR_PUBLIC_IP

# Run deployment script
curl -fsSL https://raw.githubusercontent.com/YOUR_REPO/modular_trade_agent/main/docker/deploy-oracle.sh | bash
```

### Manual Deploy
```bash
# 1. Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# 2. Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 3. Clone repository
cd /home/ubuntu
git clone https://github.com/YOUR_REPO/modular_trade_agent.git
cd modular_trade_agent

# 4. Create .env file
cat > .env <<EOF
DB_URL=sqlite:///./data/app.db
TZ=Asia/Kolkata
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeThisPassword123!
ADMIN_NAME=Admin User
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
EOF

# 5. Build and start
cd docker
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 6. Check status
docker-compose -f docker-compose.yml ps
```

---

## 🔐 First Login

After starting Docker:

1. **Wait for services to start** (10-15 seconds)
2. **Access web UI**: http://localhost:5173
3. **Login with admin credentials**:
   - Email: (value from `ADMIN_EMAIL` in `.env`)
   - Password: (value from `ADMIN_PASSWORD` in `.env`)
4. **Change password** immediately after first login (recommended)

---

## 🐛 Troubleshooting

### Port Already Allocated
```bash
# Find process using port
netstat -ano | findstr :5173  # Windows
lsof -i :5173                 # Linux/Mac

# Stop and remove containers
docker-compose -f docker-compose.yml down

# Restart
docker-compose -f docker-compose.yml up -d
```

### Can't Access Web UI (404)
- Check if container is running: `docker-compose -f docker-compose.yml ps`
- Check logs: `docker-compose -f docker-compose.yml logs web-frontend`
- Rebuild web frontend: `docker-compose -f docker-compose.yml build web-frontend`

### Login Fails
- Verify admin user exists: Check logs for `[Startup] Creating admin user`
- Verify `.env` has `ADMIN_EMAIL` and `ADMIN_PASSWORD` set
- Check API logs: `docker-compose -f docker-compose.yml logs api-server`

### Database Issues
- Delete database to reset: `Remove-Item data\app.db` (Windows) or `rm data/app.db` (Linux/Mac)
- Restart API server: `docker-compose -f docker-compose.yml restart api-server`
- Admin user will be auto-created if DB is empty

### Services Not Starting
```bash
# Check all logs
docker-compose -f docker-compose.yml logs

# Rebuild everything
docker-compose -f docker-compose.yml build --no-cache
docker-compose -f docker-compose.yml up -d
```

---

## 📁 Project Structure

```
docker/
├── Dockerfile              # Main trading service
├── Dockerfile.api          # FastAPI server
├── Dockerfile.web          # React frontend (production)
├── Dockerfile.web.dev      # React frontend (development)
├── docker-compose.yml      # Main orchestration
├── docker-compose.dev.yml  # Development overrides
├── docker-compose.prod.yml # Production overrides
├── docker-quickstart.sh    # Quick start (Linux/Mac)
├── docker-quickstart.ps1   # Quick start (Windows)
└── README.md              # This file
```

**Note:** All paths in `docker-compose.yml` are relative to the **project root**, not the `docker/` folder.

---

## 🔄 Environment-Specific Configs

### Development (Windows Local)
- Uses `docker-compose.dev.yml`
- Hot reload enabled
- Source code mounted

### Production (Oracle Ubuntu)
- Uses `docker-compose.prod.yml`
- Resource limits optimized for free tier
- Named volumes for data persistence

---

## 📝 Notes

- **Credentials**: All broker and Telegram credentials are stored encrypted in the database via web UI
- **Admin User**: Auto-created only on first deployment (when DB is empty)
- **Database**: SQLite by default (can switch to PostgreSQL)
- **Ports**:
  - Web: 5173
  - API: 8000

---

## 🆘 Need Help?

1. Check logs: `docker-compose -f docker-compose.yml logs -f`
2. Verify services are running: `docker-compose -f docker-compose.yml ps`
3. Check `.env` file exists and has required variables
4. Ensure Docker Desktop is running
