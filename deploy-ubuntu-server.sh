#!/bin/bash

################################################################################
# Rebound — Modular Trade Agent - Ubuntu Server Deployment Script
# 
# This script automates the deployment of the application to an Ubuntu server.
# It handles:
# - Docker installation
# - Application setup
# - Environment configuration
# - Reverse proxy with Nginx
# - SSL certificate with Let's Encrypt
#
# Usage: 
#   chmod +x deploy-ubuntu-server.sh
#   sudo ./deploy-ubuntu-server.sh
#
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
APP_DIR="/opt/rebound-trade-agent"
DOMAIN=""
EMAIL=""
ADMIN_EMAIL=""
ADMIN_PASSWORD=""

echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}    Rebound — Modular Trade Agent${NC}"
echo -e "${CYAN}    Ubuntu Server Deployment${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}✗ Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
USER_HOME=$(eval echo "~$ACTUAL_USER")

echo -e "${GREEN}✓ Running as root${NC}"
echo -e "${GREEN}✓ Target user: $ACTUAL_USER${NC}"
echo ""

################################################################################
# Collect Deployment Information
################################################################################

echo -e "${BLUE}[INFO] Configuration${NC}"
echo ""

# Ask for domain name
read -p "Enter your domain name (e.g., trade.yourdomain.com) [Press Enter to skip SSL]: " DOMAIN

# Ask for email for Let's Encrypt
if [ -n "$DOMAIN" ]; then
    read -p "Enter email for Let's Encrypt notifications: " EMAIL
    if [ -z "$EMAIL" ]; then
        echo -e "${YELLOW}⚠ Warning: Email required for Let's Encrypt${NC}"
        read -p "Enter email for Let's Encrypt notifications: " EMAIL
    fi
fi

# Ask for admin credentials
read -p "Enter admin email [admin@example.com]: " ADMIN_EMAIL
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@example.com}

read -sp "Enter admin password (will be hidden): " ADMIN_PASSWORD
echo ""
if [ -z "$ADMIN_PASSWORD" ]; then
    echo -e "${RED}✗ Error: Admin password is required${NC}"
    exit 1
fi

# Confirm deployment
echo ""
echo -e "${BLUE}Deployment Configuration:${NC}"
echo -e "  Domain: ${CYAN}${DOMAIN:-Not set (HTTP only)}${NC}"
echo -e "  Email: ${CYAN}${EMAIL:-Not set}${NC}"
echo -e "  Admin Email: ${CYAN}${ADMIN_EMAIL}${NC}"
echo -e "  Installation Directory: ${CYAN}${APP_DIR}${NC}"
echo ""
read -p "Continue with deployment? (y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Deployment cancelled${NC}"
    exit 0
fi

################################################################################
# Step 1: Update System
################################################################################

echo ""
echo -e "${BLUE}[1/9] Updating system packages...${NC}"
apt-get update
apt-get upgrade -y
echo -e "${GREEN}✓ System updated${NC}"

################################################################################
# Step 2: Install Docker
################################################################################

echo ""
echo -e "${BLUE}[2/9] Installing Docker...${NC}"

if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓ Docker already installed${NC}"
    docker --version
else
    echo -e "${YELLOW}Installing Docker...${NC}"
    
    # Install prerequisites
    apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    # Set up repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker Engine
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Add user to docker group
    usermod -aG docker $ACTUAL_USER
    
    echo -e "${GREEN}✓ Docker installed${NC}"
fi

# Verify Docker Compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}✗ Error: Docker Compose not available${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker Compose available${NC}"

################################################################################
# Step 3: Create Application Directory
################################################################################

echo ""
echo -e "${BLUE}[3/9] Setting up application directory...${NC}"

if [ -d "$APP_DIR" ]; then
    echo -e "${YELLOW}Directory exists. Backing up...${NC}"
    BACKUP_DIR="${APP_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
    mv "$APP_DIR" "$BACKUP_DIR"
    echo -e "${GREEN}✓ Backed up to $BACKUP_DIR${NC}"
fi

mkdir -p "$APP_DIR"
chown -R $ACTUAL_USER:$ACTUAL_USER "$APP_DIR"
echo -e "${GREEN}✓ Application directory created: $APP_DIR${NC}"

################################################################################
# Step 4: Clone/Copy Application
################################################################################

echo ""
echo -e "${BLUE}[4/9] Setting up application files...${NC}"

if [ -d "$PROJECT_DIR/.git" ]; then
    echo -e "${YELLOW}Copying application files...${NC}"
    # Copy all files except .git, node_modules, __pycache__, etc.
    rsync -av --progress \
        --exclude='.git' \
        --exclude='node_modules' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.venv' \
        --exclude='htmlcov' \
        --exclude='dist' \
        --exclude='build' \
        --exclude='*.egg-info' \
        --exclude='data/app.db' \
        --exclude='data/app.dev.db' \
        "$PROJECT_DIR/" "$APP_DIR/"
    
    chown -R $ACTUAL_USER:$ACTUAL_USER "$APP_DIR"
    echo -e "${GREEN}✓ Application files copied${NC}"
else
    echo -e "${YELLOW}Git repository not found. Please clone the repository manually:${NC}"
    echo "  git clone <repository-url> $APP_DIR"
    echo ""
    read -p "Press Enter when repository is cloned..." 
fi

################################################################################
# Step 5: Create Environment File
################################################################################

echo ""
echo -e "${BLUE}[5/9] Creating environment configuration...${NC}"

# Generate encryption key
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || openssl rand -base64 32)

cat > "$APP_DIR/.env" <<EOF
# Database
DB_URL=sqlite:///./data/app.db

# Timezone
TZ=Asia/Kolkata

# Admin User (auto-created on first deployment)
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
ADMIN_NAME=Admin User

# Encryption key for credential encryption
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# Server configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# CORS (update with your domain)
CORS_ALLOW_ORIGINS=http://localhost:5173${DOMAIN:+,https://${DOMAIN}}

# Optional: Telegram Bot Token (configure via web UI)
# TELEGRAM_BOT_TOKEN=

# Optional: Email Notifications (configure via web UI)
# SMTP_HOST=
# SMTP_PORT=587
# SMTP_USER=
# SMTP_PASSWORD=
# SMTP_FROM_EMAIL=
# SMTP_USE_TLS=true
EOF

chown $ACTUAL_USER:$ACTUAL_USER "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"
echo -e "${GREEN}✓ Environment file created${NC}"

################################################################################
# Step 6: Build and Start Docker Containers
################################################################################

echo ""
echo -e "${BLUE}[6/9] Building and starting Docker containers...${NC}"

cd "$APP_DIR/docker"

# Build images
echo -e "${YELLOW}Building Docker images (this may take several minutes)...${NC}"
sudo -u $ACTUAL_USER docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start containers
echo -e "${YELLOW}Starting containers...${NC}"
sudo -u $ACTUAL_USER docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Wait for services to start
echo -e "${YELLOW}Waiting for services to start...${NC}"
sleep 10

# Check if services are running
if docker ps | grep -q tradeagent-api && docker ps | grep -q tradeagent-web; then
    echo -e "${GREEN}✓ Services started successfully${NC}"
else
    echo -e "${RED}✗ Error: Services failed to start${NC}"
    echo -e "${YELLOW}Checking logs...${NC}"
    docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50
    exit 1
fi

################################################################################
# Step 7: Install and Configure Nginx
################################################################################

echo ""
echo -e "${BLUE}[7/9] Installing and configuring Nginx...${NC}"

# Install Nginx
if ! command -v nginx &> /dev/null; then
    apt-get install -y nginx
fi

# Create Nginx configuration
NGINX_CONFIG="/etc/nginx/sites-available/rebound-trade-agent"

cat > "$NGINX_CONFIG" <<EOF
# Upstream API server
upstream api_backend {
    server localhost:8000;
}

# HTTP server (redirects to HTTPS if SSL enabled, otherwise serves content)
server {
    listen 80;
    server_name ${DOMAIN:-_};
    
    # Increase body size for file uploads
    client_max_body_size 10M;

    # Web frontend
    location / {
        proxy_pass http://localhost:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }

    # API proxy
    location /api/ {
        proxy_pass http://api_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Health check
    location /health {
        proxy_pass http://api_backend/health;
        proxy_set_header Host \$host;
    }
}
EOF

# Enable site
ln -sf "$NGINX_CONFIG" /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test and reload Nginx
nginx -t
systemctl reload nginx

echo -e "${GREEN}✓ Nginx configured${NC}"

################################################################################
# Step 8: Setup SSL with Let's Encrypt (if domain provided)
################################################################################

if [ -n "$DOMAIN" ]; then
    echo ""
    echo -e "${BLUE}[8/9] Setting up SSL with Let's Encrypt...${NC}"
    
    # Install Certbot
    if ! command -v certbot &> /dev/null; then
        apt-get install -y certbot python3-certbot-nginx
    fi
    
    # Obtain certificate
    echo -e "${YELLOW}Obtaining SSL certificate...${NC}"
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "$EMAIL" --redirect
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ SSL certificate installed${NC}"
        
        # Update CORS in .env file
        sed -i "s|CORS_ALLOW_ORIGINS=.*|CORS_ALLOW_ORIGINS=https://${DOMAIN}|" "$APP_DIR/.env"
        
        # Restart API server to pick up new CORS settings
        cd "$APP_DIR/docker"
        docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api-server
        
        echo -e "${GREEN}✓ CORS configuration updated${NC}"
    else
        echo -e "${YELLOW}⚠ Warning: SSL certificate installation failed${NC}"
        echo -e "${YELLOW}You can run certbot manually: certbot --nginx -d $DOMAIN${NC}"
    fi
else
    echo ""
    echo -e "${BLUE}[8/9] Skipping SSL setup (no domain provided)${NC}"
    echo -e "${YELLOW}⚠ Running in HTTP mode only${NC}"
    echo -e "${YELLOW}To add SSL later, run: certbot --nginx -d yourdomain.com${NC}"
fi

################################################################################
# Step 9: Configure Firewall
################################################################################

echo ""
echo -e "${BLUE}[9/9] Configuring firewall...${NC}"

if command -v ufw &> /dev/null; then
    # Allow HTTP
    ufw allow 80/tcp
    echo -e "${GREEN}✓ HTTP (port 80) allowed${NC}"
    
    # Allow HTTPS if SSL was configured
    if [ -n "$DOMAIN" ]; then
        ufw allow 443/tcp
        echo -e "${GREEN}✓ HTTPS (port 443) allowed${NC}"
    fi
    
    # Allow SSH (if not already allowed)
    ufw allow 22/tcp || true
    
    # Enable firewall if not already enabled
    ufw --force enable 2>/dev/null || true
    
    echo -e "${GREEN}✓ Firewall configured${NC}"
else
    echo -e "${YELLOW}⚠ UFW not found. Please configure firewall manually${NC}"
fi

################################################################################
# Deployment Complete
################################################################################

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Deployment Complete!${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Determine access URL
if [ -n "$DOMAIN" ]; then
    ACCESS_URL="https://${DOMAIN}"
else
    SERVER_IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')
    ACCESS_URL="http://${SERVER_IP}"
fi

echo -e "${BLUE}📋 Deployment Summary:${NC}"
echo -e "  Installation Directory: ${CYAN}${APP_DIR}${NC}"
echo -e "  Access URL: ${CYAN}${ACCESS_URL}${NC}"
echo -e "  Admin Email: ${CYAN}${ADMIN_EMAIL}${NC}"
echo -e "  Domain: ${CYAN}${DOMAIN:-Not configured}${NC}"
echo ""

echo -e "${BLUE}🔧 Management Commands:${NC}"
echo -e "  View logs:        ${CYAN}cd ${APP_DIR}/docker && docker compose logs -f${NC}"
echo -e "  Restart services: ${CYAN}cd ${APP_DIR}/docker && docker compose restart${NC}"
echo -e "  Stop services:    ${CYAN}cd ${APP_DIR}/docker && docker compose down${NC}"
echo -e "  Start services:   ${CYAN}cd ${APP_DIR}/docker && docker compose up -d${NC}"
echo ""

echo -e "${BLUE}🌐 Access Application:${NC}"
echo -e "  Web UI: ${CYAN}${ACCESS_URL}${NC}"
echo -e "  API: ${CYAN}${ACCESS_URL}/api${NC}"
echo -e "  Health: ${CYAN}${ACCESS_URL}/api/health${NC}"
echo ""

echo -e "${BLUE}🔐 First Login:${NC}"
echo -e "  Email: ${CYAN}${ADMIN_EMAIL}${NC}"
echo -e "  Password: ${CYAN}[The password you entered]${NC}"
echo -e ""
echo -e "${YELLOW}⚠ Important: Change your password after first login!${NC}"
echo ""

if [ -n "$DOMAIN" ]; then
    echo -e "${BLUE}🔒 SSL Certificate:${NC}"
    echo -e "  Certificate will auto-renew via certbot timer"
    echo -e "  Test renewal: ${CYAN}sudo certbot renew --dry-run${NC}"
    echo ""
fi

echo -e "${BLUE}📚 Documentation:${NC}"
echo -e "  Deployment Guide: ${CYAN}docs/DEPLOYMENT.md${NC}"
echo -e "  Docker Guide: ${CYAN}docker/README.md${NC}"
echo ""

echo -e "${GREEN}Happy Trading! 📈${NC}"
echo ""

