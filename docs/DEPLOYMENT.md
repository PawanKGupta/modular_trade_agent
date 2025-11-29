# Deployment Guide

Complete guide for deploying the Modular Trade Agent to production.

## Deployment Options

### Option 1: Docker (Recommended)

The easiest and most reliable deployment method.

#### Prerequisites
- Docker and Docker Compose installed
- Domain name (optional, for production)
- SSL certificate (optional, for HTTPS)

#### Steps

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd modular_trade_agent
   ```

2. **Configure Environment**
   ```bash
   # Create .env file
   cp .env.example .env

   # Edit .env with production values
   DB_URL=postgresql://user:password@db:5432/tradeagent
   ADMIN_EMAIL=admin@yourdomain.com
   ADMIN_PASSWORD=secure-password
   JWT_SECRET=your-secure-random-secret
   ENCRYPTION_KEY=your-encryption-key
   CORS_ALLOW_ORIGINS=https://yourdomain.com
   ```

3. **Deploy**
   ```bash
   cd docker
   docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

4. **Verify**
   ```bash
   # Check services
   docker-compose ps

   # View logs
   docker-compose logs -f

   # Test health
   curl http://localhost:8000/health
   ```

#### Production Considerations

- **Database:** Use PostgreSQL instead of SQLite
- **Reverse Proxy:** Use Nginx for SSL termination
- **Backups:** Set up regular database backups
- **Monitoring:** Configure logging and monitoring
- **Security:** Use strong passwords and secrets

See [docker/README.md](../docker/README.md) for detailed Docker documentation.

### Option 2: Manual Deployment

For custom deployments or specific requirements.

#### Backend Deployment

1. **Server Setup**
   ```bash
   # Install Python 3.12+
   sudo apt update
   sudo apt install python3.12 python3.12-venv

   # Create application directory
   mkdir -p /opt/tradeagent
   cd /opt/tradeagent
   ```

2. **Application Setup**
   ```bash
   # Clone repository
   git clone <repository-url> .

   # Create virtual environment
   python3.12 -m venv .venv
   source .venv/bin/activate

   # Install dependencies
   pip install -r requirements.txt
   pip install -r server/requirements.txt
   ```

3. **Database Setup**
   ```bash
   # Install PostgreSQL (recommended)
   sudo apt install postgresql postgresql-contrib

   # Create database
   sudo -u postgres psql
   CREATE DATABASE tradeagent;
   CREATE USER tradeagent WITH PASSWORD 'secure-password';
   GRANT ALL PRIVILEGES ON DATABASE tradeagent TO tradeagent;
   \q
   ```

4. **Configure Environment**
   ```bash
   # Create .env file
   DB_URL=postgresql://tradeagent:secure-password@localhost:5432/tradeagent
   ADMIN_EMAIL=admin@yourdomain.com
   ADMIN_PASSWORD=secure-password
   JWT_SECRET=your-secure-random-secret
   ENCRYPTION_KEY=your-encryption-key
   ```

5. **Run Migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start with Systemd**
   ```bash
   # Create systemd service file
   sudo nano /etc/systemd/system/tradeagent-api.service
   ```

   ```ini
   [Unit]
   Description=Trade Agent API
   After=network.target postgresql.service

   [Service]
   Type=simple
   User=tradeagent
   WorkingDirectory=/opt/tradeagent
   Environment="PATH=/opt/tradeagent/.venv/bin"
   ExecStart=/opt/tradeagent/.venv/bin/uvicorn server.app.main:app --host 0.0.0.0 --port 8000
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   # Enable and start service
   sudo systemctl daemon-reload
   sudo systemctl enable tradeagent-api
   sudo systemctl start tradeagent-api
   ```

#### Frontend Deployment

1. **Build Frontend**
   ```bash
   cd web
   npm install
   npm run build
   ```

2. **Serve with Nginx**
   ```bash
   # Install Nginx
   sudo apt install nginx

   # Create Nginx config
   sudo nano /etc/nginx/sites-available/tradeagent
   ```

   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;

       root /opt/tradeagent/web/dist;
       index index.html;

       # SPA routing
       location / {
           try_files $uri $uri/ /index.html;
       }

       # API proxy
       location /api/ {
           proxy_pass http://localhost:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_cache_bypass $http_upgrade;
       }
   }
   ```

   ```bash
   # Enable site
   sudo ln -s /etc/nginx/sites-available/tradeagent /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

3. **SSL with Let's Encrypt**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```

## Environment-Specific Configurations

### Development
- SQLite database
- Debug mode enabled
- CORS allows localhost
- Hot reload enabled

### Production
- PostgreSQL database
- Debug mode disabled
- CORS restricted to domain
- Production optimizations
- SSL/TLS enabled

## Database Migrations

### Using Alembic

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Manual Schema Creation

If not using Alembic, the application will auto-create tables on first run (development only).

## Backup and Recovery

### Database Backup

```bash
# PostgreSQL backup
pg_dump -U tradeagent tradeagent > backup_$(date +%Y%m%d).sql

# SQLite backup
cp data/app.db data/app.db.backup
```

### Automated Backups

```bash
# Create backup script
#!/bin/bash
BACKUP_DIR=/opt/tradeagent/backups
mkdir -p $BACKUP_DIR
pg_dump -U tradeagent tradeagent > $BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql
find $BACKUP_DIR -name "backup_*.sql" -mtime +7 -delete

# Add to crontab
0 2 * * * /opt/tradeagent/scripts/backup.sh
```

### Recovery

```bash
# Restore from backup
psql -U tradeagent tradeagent < backup_20250115.sql
```

## Monitoring

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Expected response: {"status": "ok"}
```

### Log Monitoring

```bash
# View logs
tail -f logs/server_api.log

# Docker logs
docker-compose logs -f api-server
```

### System Monitoring

- Monitor disk space
- Monitor database size
- Monitor API response times
- Set up alerts for errors

## Security Checklist

- [ ] Strong admin password
- [ ] Secure JWT secret (random, long)
- [ ] Encryption key for credentials
- [ ] CORS properly configured
- [ ] SSL/TLS enabled (production)
- [ ] Database credentials secure
- [ ] Regular security updates
- [ ] Firewall configured
- [ ] Backups automated
- [ ] Logs monitored

## Scaling Considerations

### Current Limitations
- Single instance deployment
- SQLite not suitable for high concurrency

### Scaling Options

1. **Database:**
   - Use PostgreSQL for production
   - Consider read replicas for high read load

2. **Application:**
   - Run multiple API instances behind load balancer
   - Use process manager (Gunicorn with multiple workers)

3. **Caching:**
   - Add Redis for caching
   - Cache frequently accessed data

4. **Static Assets:**
   - Use CDN for frontend assets
   - Enable compression

## Troubleshooting

### Service Won't Start
- Check logs: `docker-compose logs` or `journalctl -u tradeagent-api`
- Verify environment variables
- Check database connectivity
- Verify port availability

### Database Connection Errors
- Verify database is running
- Check connection string in `.env`
- Verify credentials
- Check firewall rules

### Frontend Not Loading
- Check Nginx configuration
- Verify build output exists
- Check browser console for errors
- Verify API proxy configuration

### Performance Issues
- Check database query performance
- Monitor resource usage (CPU, memory)
- Review slow queries
- Consider caching

## Maintenance

### Regular Tasks
- Monitor logs for errors
- Review database size
- Check disk space
- Update dependencies
- Review security patches
- Test backups

### Updates
```bash
# Pull latest code
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade
cd web && npm update

# Run migrations
alembic upgrade head

# Restart services
docker-compose restart
# or
sudo systemctl restart tradeagent-api
```
