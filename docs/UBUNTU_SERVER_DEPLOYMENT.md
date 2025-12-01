# Ubuntu Server Deployment Guide

Complete guide for deploying Rebound — Modular Trade Agent to an Ubuntu server.

## 🚀 Quick Deploy

### Automated Deployment (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd modular_trade_agent

# Run deployment script
chmod +x deploy-ubuntu-server.sh
sudo ./deploy-ubuntu-server.sh
```

The script will:
1. ✅ Update system packages
2. ✅ Install Docker and Docker Compose
3. ✅ Set up application directory
4. ✅ Configure environment variables
5. ✅ Build and start Docker containers
6. ✅ Configure Nginx reverse proxy
7. ✅ Set up SSL certificate (if domain provided)
8. ✅ Configure firewall

### Manual Deployment

Follow the step-by-step guide below if you prefer manual setup.

---

## 📋 Prerequisites

### Server Requirements

- **OS**: Ubuntu 20.04 LTS or later (22.04 LTS recommended)
- **RAM**: Minimum 2GB (4GB recommended)
- **CPU**: 2 cores minimum
- **Disk**: 10GB free space minimum
- **Network**: Static IP or domain name
- **Access**: SSH access with sudo privileges

### Domain (Optional but Recommended)

- Domain name pointing to your server IP
- DNS A record configured
- Ports 80 and 443 open in firewall

---

## 📦 Step-by-Step Manual Deployment

### Step 1: Update System

```bash
sudo apt update
sudo apt upgrade -y
```

### Step 2: Install Docker

```bash
# Install prerequisites
sudo apt install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Set up repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in for group changes to take effect
# Or use: newgrp docker

# Verify installation
docker --version
docker compose version
```

### Step 3: Clone Repository

```bash
# Create application directory
sudo mkdir -p /opt/rebound-trade-agent
sudo chown $USER:$USER /opt/rebound-trade-agent

# Clone repository
cd /opt
git clone <repository-url> rebound-trade-agent
cd rebound-trade-agent
```

### Step 4: Configure Environment

```bash
# Create .env file
cat > .env <<EOF
# Database
DB_URL=sqlite:///./data/app.db

# Timezone
TZ=Asia/Kolkata

# Admin User (auto-created on first deployment)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeThisPassword123!
ADMIN_NAME=Admin User

# Encryption key (generate with Python)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Server configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# CORS (update with your domain)
CORS_ALLOW_ORIGINS=http://localhost:5173

# Optional: Telegram/Email (configure via web UI)
EOF

# Secure the .env file
chmod 600 .env
```

### Step 5: Build and Start Containers

```bash
cd docker

# Build images
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### Step 6: Install Nginx

```bash
sudo apt install -y nginx
```

### Step 7: Configure Nginx

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/rebound-trade-agent
```

Add the following configuration:

```nginx
# Upstream API server
upstream api_backend {
    server localhost:8000;
}

server {
    listen 80;
    server_name yourdomain.com;  # Replace with your domain

    client_max_body_size 10M;

    # Web frontend
    location / {
        proxy_pass http://localhost:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # API proxy
    location /api/ {
        proxy_pass http://api_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Health check
    location /health {
        proxy_pass http://api_backend/health;
        proxy_set_header Host $host;
    }
}
```

Enable the site:

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/rebound-trade-agent /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### Step 8: Setup SSL (Optional but Recommended)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d yourdomain.com

# Test automatic renewal
sudo certbot renew --dry-run
```

Certbot will automatically:
- Obtain SSL certificate
- Configure Nginx for HTTPS
- Set up automatic renewal

### Step 9: Configure Firewall

```bash
# Allow HTTP
sudo ufw allow 80/tcp

# Allow HTTPS
sudo ufw allow 443/tcp

# Allow SSH (if not already allowed)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

---

## 🔧 Management Commands

### Docker Services

```bash
cd /opt/rebound-trade-agent/docker

# View logs
docker compose logs -f

# Restart services
docker compose restart

# Stop services
docker compose down

# Start services
docker compose up -d

# Rebuild after code changes
docker compose build
docker compose up -d
```

### Service Status

```bash
# Check Docker containers
docker ps

# Check Nginx status
sudo systemctl status nginx

# Check SSL certificate
sudo certbot certificates
```

---

## 🔄 Updates and Maintenance

### Update Application

```bash
cd /opt/rebound-trade-agent

# Pull latest code
git pull origin main

# Rebuild and restart
cd docker
docker compose build
docker compose restart
```

### Database Migrations

Migrations run automatically on startup. To run manually:

```bash
cd /opt/rebound-trade-agent/docker
docker compose exec api-server python -m alembic upgrade head
```

### Backup

```bash
# Backup database
cp /opt/rebound-trade-agent/data/app.db /opt/rebound-trade-agent/data/app.db.backup.$(date +%Y%m%d)

# Backup configuration
tar -czf backup-$(date +%Y%m%d).tar.gz /opt/rebound-trade-agent/.env /opt/rebound-trade-agent/data
```

### Automated Backups

Create a backup script:

```bash
sudo nano /usr/local/bin/backup-rebound.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/rebound-trade-agent/backups"
mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/backup-$(date +%Y%m%d_%H%M%S).tar.gz \
    /opt/rebound-trade-agent/.env \
    /opt/rebound-trade-agent/data
find $BACKUP_DIR -name "backup-*.tar.gz" -mtime +7 -delete
```

Make executable and add to crontab:

```bash
sudo chmod +x /usr/local/bin/backup-rebound.sh

# Add to crontab (run daily at 2 AM)
sudo crontab -e
# Add line:
# 0 2 * * * /usr/local/bin/backup-rebound.sh
```

---

## 🐛 Troubleshooting

### Services Not Starting

```bash
# Check Docker logs
cd /opt/rebound-trade-agent/docker
docker compose logs api-server
docker compose logs web-frontend

# Check container status
docker compose ps

# Restart services
docker compose restart
```

### Nginx Not Working

```bash
# Test Nginx configuration
sudo nginx -t

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log

# Restart Nginx
sudo systemctl restart nginx
```

### SSL Certificate Issues

```bash
# Check certificate status
sudo certbot certificates

# Renew certificate manually
sudo certbot renew

# Test renewal
sudo certbot renew --dry-run
```

### Port Conflicts

```bash
# Check what's using port 8000
sudo lsof -i :8000

# Check what's using port 5173
sudo lsof -i :5173

# Stop conflicting services
sudo systemctl stop <service-name>
```

### Database Issues

```bash
# Check database file
ls -lh /opt/rebound-trade-agent/data/app.db

# View database logs
docker compose logs api-server | grep -i database

# Reset database (WARNING: This deletes all data)
cd /opt/rebound-trade-agent/docker
docker compose down
rm -f ../data/app.db
docker compose up -d
```

---

## 🔐 Security Checklist

- [ ] Strong admin password set
- [ ] `.env` file permissions set to 600
- [ ] Firewall configured (UFW)
- [ ] SSL certificate installed (if using domain)
- [ ] Regular backups configured
- [ ] System packages up to date
- [ ] Docker images regularly updated
- [ ] Logs monitored for errors
- [ ] SSH access secured (key-based auth recommended)

---

## 📚 Additional Resources

- [Docker Documentation](../docker/README.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [API Documentation](./API.md)
- [User Guide](./USER_GUIDE.md)

---

## 🆘 Getting Help

If you encounter issues:

1. Check logs: `docker compose logs -f`
2. Verify configuration: Review `.env` file
3. Test connectivity: `curl http://localhost:8000/health`
4. Check system resources: `htop` or `free -h`
5. Review documentation: See links above

---

**Note**: For production deployments, consider:
- Using PostgreSQL instead of SQLite
- Setting up monitoring and alerting
- Implementing log rotation
- Configuring automated backups
- Using a reverse proxy with rate limiting
- Setting up failover/redundancy

