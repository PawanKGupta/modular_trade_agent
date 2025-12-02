# Accessing the Web UI

After successful deployment, access your application:

## Web UI Access

**URL:** `http://YOUR_SERVER_IP:5173`

## API Server Access

**URL:** `http://YOUR_SERVER_IP:8000`
- Health check: `http://YOUR_SERVER_IP:8000/health`
- API docs: `http://YOUR_SERVER_IP:8000/docs`

## Verify Containers Are Running

```bash
# Check container status
docker ps

# Check logs if needed
docker logs tradeagent-web
docker logs tradeagent-api

# Check if ports are listening
sudo netstat -tlnp | grep -E '5173|8000'
```

## Find Your Server IP

```bash
# Public IP
curl ifconfig.me

# OR all IPs
hostname -I
```

## Oracle Cloud Firewall Configuration

Make sure these ports are open in Oracle Cloud Security Rules:

1. **Port 5173** - Web UI (HTTP)
2. **Port 8000** - API Server (HTTP)

### Steps to Open Ports in Oracle Cloud:

1. Go to **Networking** → **Virtual Cloud Networks**
2. Select your VCN → **Security Lists**
3. Click on **Default Security List**
4. Click **Add Ingress Rules**
5. Add rules for:
   - **Source:** `0.0.0.0/0`
   - **IP Protocol:** TCP
   - **Destination Port Range:** `5173` (for Web UI)
   - **Source:** `0.0.0.0/0`
   - **IP Protocol:** TCP
   - **Destination Port Range:** `8000` (for API)

## Troubleshooting

### Containers Not Running

```bash
# Check container status
docker ps -a

# View logs
docker logs tradeagent-web
docker logs tradeagent-api

# Restart containers
cd ~/modular_trade_agent/docker
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart
```

### Can't Access from Browser

1. **Check firewall on server:**
   ```bash
   sudo ufw status
   sudo ufw allow 5173/tcp
   sudo ufw allow 8000/tcp
   ```

2. **Verify Oracle Cloud Security Rules** (see above)

3. **Check if ports are listening:**
   ```bash
   sudo netstat -tlnp | grep -E '5173|8000'
   ```

4. **Test locally on server:**
   ```bash
   curl http://localhost:5173
   curl http://localhost:8000/health
   ```
