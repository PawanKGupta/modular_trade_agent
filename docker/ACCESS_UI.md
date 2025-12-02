# Accessing the Web UI

After successful deployment, access your application:

## Web UI Access

**URL:** `http://YOUR_SERVER_IP:5173`

## API Server Access

**URL:** `http://YOUR_SERVER_IP:8000`
- Health check: `http://YOUR_SERVER_IP:8000/health`
- API docs: `http://YOUR_SERVER_IP:8000/docs`

## Finding Your Server IP

### From the Server:
```bash
# Public IP
curl ifconfig.me

# OR all IPs
hostname -I

# OR from Oracle Cloud metadata
curl -s http://169.254.169.254/opc/v1/instance/ | grep -i publicIp
```

### From Oracle Cloud Console:
1. Go to **Compute** → **Instances**
2. Click on your instance
3. Find **Public IP address** in the details

## IP Address Changes

### What Happens if IP Changes?

✅ **API Calls Continue Working** - The frontend uses relative URLs (`/api/v1`), so API calls will work regardless of IP changes.

❌ **You Need to Update Browser URL** - You'll need to access the app using the new IP address.

### Solutions for IP Stability:

#### 1. **Static IP (Recommended for Production)**

Reserve a static public IP in Oracle Cloud:

1. Go to **Networking** → **IP Management** → **Reserved Public IPs**
2. Click **Create Reserved Public IP**
3. Choose **Regional** scope
4. Assign it to your compute instance
5. **Result:** IP never changes, even after restart

#### 2. **Use a Domain Name**

Point a domain to your server:

1. Buy/use a domain (e.g., from Namecheap, Cloudflare, etc.)
2. Create an **A Record** pointing to your server IP:
   ```
   yourdomain.com → YOUR_SERVER_IP
   ```
3. Access via: `http://yourdomain.com:5173`
4. **Note:** Update DNS A record if IP changes

#### 3. **Dynamic DNS (Auto-Update)**

If IP changes frequently, use Dynamic DNS:

- Services: No-IP, DuckDNS, Cloudflare Dynamic DNS
- Script runs on server to update DNS when IP changes
- Always access via same domain name

### Quick Fix: Find New IP

If your IP changed, find the new one:

```bash
# On the server
curl ifconfig.me

# Then update your browser bookmark/URL to:
# http://NEW_IP:5173
```

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
