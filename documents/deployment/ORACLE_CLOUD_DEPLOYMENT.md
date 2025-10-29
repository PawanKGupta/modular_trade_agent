# Oracle Cloud Deployment Guide

## Automated Trading System on Oracle Cloud Infrastructure (OCI)

This guide shows how to deploy your automated trading system on **Oracle Cloud Free Tier** or paid instances.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Free Tier vs Paid Options](#free-tier-vs-paid-options)
4. [Deployment Steps](#deployment-steps)
5. [Schedule Configuration](#schedule-configuration)
6. [Monitoring & Logs](#monitoring--logs)
7. [Troubleshooting](#troubleshooting)
8. [Cost Optimization](#cost-optimization)

---

## Architecture Overview

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Oracle Cloud Infrastructure             │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Compute Instance (VM.Standard.E2.1.Micro)       │   │
│  │  - Ubuntu 22.04 LTS (ARM/x86)                    │   │
│  │  - 1 GB RAM (Free Tier) or more                  │   │
│  │  - Always-Free eligible                          │   │
│  ├──────────────────────────────────────────────────┤   │
│  │                                                    │   │
│  │  Python Application                               │   │
│  │  ├─ trade_agent (4:00 PM analysis)              │   │
│  │  ├─ buy orders (4:00 PM AMO)                     │   │
│  │  └─ sell orders (9:15 AM - 3:30 PM)             │   │
│  │                                                    │   │
│  │  Systemd Services                                 │   │
│  │  ├─ trading-buy.service (timer: 16:00)          │   │
│  │  └─ trading-sell.service (timer: 09:15)         │   │
│  │                                                    │   │
│  │  Monitoring                                       │   │
│  │  ├─ Application logs → /var/log/trading/        │   │
│  │  └─ OCI Monitoring (metrics & alerts)           │   │
│  │                                                    │   │
│  └──────────────────────────────────────────────────┘   │
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Object Storage (Optional)                        │   │
│  │  - Trade history backups                          │   │
│  │  - Analysis results archive                       │   │
│  │  - Free: 10 GB + 50 GB Archive                   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Notifications (Optional)                         │   │
│  │  - Email/SMS alerts on order failures             │   │
│  │  - Telegram integration for updates               │   │
│  └──────────────────────────────────────────────────┘   │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### Daily Workflow

```
4:00 PM  → Backtest & Analysis → Generate Recommendations
4:01 PM  → Place AMO Buy Orders → Orders queued for tomorrow
9:15 AM  → Place Sell Orders (EMA9) → Continuous monitoring starts
9:15 AM  → Monitor & Update Orders → Every 60 seconds
3:30 PM  → Market Close → Stop monitoring, generate report
```

---

## Prerequisites

### 1. Oracle Cloud Account
- Sign up at [cloud.oracle.com](https://cloud.oracle.com/)
- Free tier includes:
  - 2 Always-Free VMs (ARM or x86)
  - 200 GB Block Storage
  - 10 GB Object Storage
  - 10 TB Outbound Transfer/month

### 2. Local Requirements
- SSH client (Windows: PowerShell/PuTTY, Linux/Mac: built-in)
- Oracle Cloud CLI (optional, for automation)
- Git (for code deployment)

### 3. API Credentials
- Kotak Neo API credentials (`kotak_neo.env`)
- Telegram Bot Token (optional, for notifications)

---

## Free Tier vs Paid Options

### Always-Free Tier (Recommended for Testing)

**Compute:**
- **VM.Standard.E2.1.Micro** (ARM-based Ampere A1)
  - 1/6 OCPU (equivalent to 1 vCPU)
  - 1 GB RAM
  - **Limit**: 2 instances per tenancy
  - **Cost**: FREE forever

**Alternative Free Tier:**
- **VM.Standard.A1.Flex** (ARM Ampere)
  - Up to 4 OCPUs
  - Up to 24 GB RAM
  - **Total free**: 4 OCPUs + 24 GB RAM shared across instances
  - **Cost**: FREE forever

**Storage:**
- 200 GB total Block Storage
- 10 GB Object Storage
- **Cost**: FREE forever

### Paid Options (Production)

**For High-Performance Trading:**

| Instance Type | OCPUs | RAM | Price (approx) | Use Case |
|---------------|-------|-----|----------------|----------|
| VM.Standard.E4.Flex | 2 | 16 GB | ~$50/month | Multiple portfolios |
| VM.Standard3.Flex | 4 | 32 GB | ~$100/month | High-frequency trading |
| VM.Optimized3.Flex | 8 | 64 GB | ~$200/month | Large-scale operations |

**Recommendation**: Start with **Free Tier (A1.Flex with 2 OCPU + 12 GB RAM)** - more than enough for 6-stock portfolio.

---

## Deployment Steps

### Step 1: Create Oracle Cloud Compute Instance

#### 1.1 Navigate to Compute Instances
```
OCI Console → Compute → Instances → Create Instance
```

#### 1.2 Configure Instance

**Name**: `trading-bot-prod`

**Placement:**
- Keep default availability domain

**Image and Shape:**
- **Image**: Ubuntu 22.04 (Minimal)
- **Shape**: 
  - Click "Change Shape"
  - Select "Ampere" (ARM-based)
  - Choose "VM.Standard.A1.Flex"
  - Set: 2 OCPUs, 12 GB RAM (adjust as needed within free tier)

**Networking:**
- **VCN**: Use default or create new
- **Subnet**: Public subnet
- **Public IP**: ✅ Assign public IPv4 address

**SSH Keys:**
- Select "Generate SSH key pair"
- Download both private and public keys
- **IMPORTANT**: Save the private key securely!

**Boot Volume:**
- Size: 50 GB (default, can increase up to 200 GB total free)

Click **Create** → Wait 1-2 minutes for provisioning

#### 1.3 Note Important Details

Once created, note:
- **Public IP Address**: e.g., `129.213.xxx.xxx`
- **Private IP Address**: e.g., `10.0.0.xxx`
- **SSH Connection**: `ssh -i private_key.pem ubuntu@PUBLIC_IP`

---

### Step 2: Configure Network Security

#### 2.1 Open Required Ports

**Navigate to:**
```
Instance Details → Virtual Cloud Network → Security Lists → Default Security List
```

**Add Ingress Rules:**

| Type | Source | Protocol | Port Range | Purpose |
|------|--------|----------|------------|---------|
| Ingress | 0.0.0.0/0 | TCP | 22 | SSH access |
| Ingress | YOUR_IP/32 | TCP | 8080 | Optional: Monitoring dashboard |

**Note**: For security, restrict SSH (port 22) to your IP only in production.

#### 2.2 Configure OS Firewall

SSH into your instance and run:

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

---

### Step 3: Initial Server Setup

#### 3.1 Connect via SSH

**Windows (PowerShell):**
```powershell
ssh -i path\to\private_key.pem ubuntu@PUBLIC_IP
```

**Linux/Mac:**
```bash
chmod 400 private_key.pem
ssh -i private_key.pem ubuntu@PUBLIC_IP
```

#### 3.2 Update System

```bash
# Update package list
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y git python3 python3-pip python3-venv htop vim curl wget
```

#### 3.3 Create Application User

```bash
# Create dedicated user for trading app
sudo adduser trading --disabled-password --gecos ""

# Add to necessary groups
sudo usermod -aG sudo trading

# Switch to trading user
sudo su - trading
```

---

### Step 4: Deploy Application

#### 4.1 Clone Repository

```bash
# As trading user
cd /home/trading

# Clone your repository (use your actual repo URL)
git clone https://github.com/YOUR_USERNAME/modular_trade_agent.git
cd modular_trade_agent

# Or upload via SCP if private repo:
# From your local machine:
# scp -i private_key.pem -r C:\Personal\Projects\TradingView\modular_trade_agent ubuntu@PUBLIC_IP:/home/trading/
```

#### 4.2 Setup Python Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install Kotak Neo SDK
pip install neo-api-client
```

#### 4.3 Configure Environment

```bash
# Create data directories
mkdir -p data/scrip_master logs analysis_results

# Copy and configure credentials
vim modules/kotak_neo_auto_trader/kotak_neo.env
```

**Add your credentials:**
```env
KOTAK_CONSUMER_KEY=your_consumer_key
KOTAK_CONSUMER_SECRET=your_consumer_secret
KOTAK_MOBILE_NUMBER=+91xxxxxxxxxx
KOTAK_PASSWORD=your_password
KOTAK_TOTP_SECRET=your_totp_secret
KOTAK_MPIN=your_mpin
KOTAK_ENVIRONMENT=prod
```

**Secure the credentials:**
```bash
chmod 600 modules/kotak_neo_auto_trader/kotak_neo.env
```

#### 4.4 Test Application

```bash
# Test authentication
python -m modules.kotak_neo_auto_trader.auth --test

# Test buy engine (dry run)
python -m modules.kotak_neo_auto_trader.run_auto_trade --env modules/kotak_neo_auto_trader/kotak_neo.env

# Test sell engine
python -m modules.kotak_neo_auto_trader.run_sell_orders --env modules/kotak_neo_auto_trader/kotak_neo.env --run-once --skip-wait
```

---

### Step 5: Create Systemd Services

#### 5.1 Buy Order Service

Create service file:
```bash
sudo vim /etc/systemd/system/trading-buy.service
```

```ini
[Unit]
Description=Trading Bot - Buy Orders (AMO)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=trading
WorkingDirectory=/home/trading/modular_trade_agent
Environment="PATH=/home/trading/modular_trade_agent/.venv/bin"
ExecStart=/home/trading/modular_trade_agent/.venv/bin/python -m modules.kotak_neo_auto_trader.run_auto_trade --env modules/kotak_neo_auto_trader/kotak_neo.env
StandardOutput=append:/var/log/trading/buy.log
StandardError=append:/var/log/trading/buy-error.log
TimeoutSec=300

[Install]
WantedBy=multi-user.target
```

#### 5.2 Sell Order Service

```bash
sudo vim /etc/systemd/system/trading-sell.service
```

```ini
[Unit]
Description=Trading Bot - Sell Orders (Monitor)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=trading
WorkingDirectory=/home/trading/modular_trade_agent
Environment="PATH=/home/trading/modular_trade_agent/.venv/bin"
ExecStart=/home/trading/modular_trade_agent/.venv/bin/python -m modules.kotak_neo_auto_trader.run_sell_orders --env modules/kotak_neo_auto_trader/kotak_neo.env --monitor-interval 60
Restart=on-failure
RestartSec=30
StandardOutput=append:/var/log/trading/sell.log
StandardError=append:/var/log/trading/sell-error.log

[Install]
WantedBy=multi-user.target
```

#### 5.3 Create Systemd Timers

**Buy Order Timer (4:00 PM daily):**
```bash
sudo vim /etc/systemd/system/trading-buy.timer
```

```ini
[Unit]
Description=Trading Bot - Buy Orders Timer (4:00 PM)
Requires=trading-buy.service

[Timer]
OnCalendar=Mon..Fri 16:00:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
```

**Sell Order Timer (9:15 AM daily):**
```bash
sudo vim /etc/systemd/system/trading-sell.timer
```

```ini
[Unit]
Description=Trading Bot - Sell Orders Timer (9:15 AM)
Requires=trading-sell.service

[Timer]
OnCalendar=Mon..Fri 09:15:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
```

#### 5.4 Setup Log Directory

```bash
# Create log directory
sudo mkdir -p /var/log/trading
sudo chown trading:trading /var/log/trading

# Setup log rotation
sudo vim /etc/logrotate.d/trading
```

```
/var/log/trading/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 trading trading
}
```

#### 5.5 Enable and Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable timers (start on boot)
sudo systemctl enable trading-buy.timer
sudo systemctl enable trading-sell.timer

# Start timers
sudo systemctl start trading-buy.timer
sudo systemctl start trading-sell.timer

# Check timer status
sudo systemctl list-timers --all | grep trading

# Check service status
sudo systemctl status trading-buy.timer
sudo systemctl status trading-sell.timer
```

---

## Schedule Configuration

### Verify Schedule

```bash
# List all active timers
systemctl list-timers

# Output should show:
# NEXT                        LEFT     LAST  PASSED  UNIT                  ACTIVATES
# Mon 2025-01-27 16:00:00 IST 8h left  n/a   n/a     trading-buy.timer    trading-buy.service
# Tue 2025-01-28 09:15:00 IST 18h left n/a   n/a     trading-sell.timer   trading-sell.service
```

### Manual Triggers (for Testing)

```bash
# Manually trigger buy service
sudo systemctl start trading-buy.service

# Check logs immediately
sudo journalctl -u trading-buy.service -f

# Manually trigger sell service
sudo systemctl start trading-sell.service

# Check logs
sudo journalctl -u trading-sell.service -f
```

### Adjust Timers (if needed)

```bash
# Edit timer
sudo systemctl edit --full trading-buy.timer

# After changes, reload
sudo systemctl daemon-reload
sudo systemctl restart trading-buy.timer
```

---

## Monitoring & Logs

### View Logs

```bash
# Real-time logs (buy)
tail -f /var/log/trading/buy.log

# Real-time logs (sell)
tail -f /var/log/trading/sell.log

# View errors
tail -f /var/log/trading/buy-error.log
tail -f /var/log/trading/sell-error.log

# Systemd logs
sudo journalctl -u trading-buy.service -n 100
sudo journalctl -u trading-sell.service -n 100 -f
```

### System Monitoring

```bash
# Check system resources
htop

# Check disk usage
df -h

# Check memory
free -h

# Check active services
systemctl status trading-*
```

### Oracle Cloud Monitoring (Optional)

#### Enable OCI Monitoring Agent

```bash
# Install OCI monitoring agent
wget https://objectstorage.us-ashburn-1.oraclecloud.com/n/idhph4hmky92/b/oci-monitoring-agent/o/oracle-unified-agent-latest.sh
chmod +x oracle-unified-agent-latest.sh
sudo ./oracle-unified-agent-latest.sh

# Configure custom metrics
sudo vim /opt/oracle-unified-agent/etc/logging-config.yaml
```

---

## Backup Configuration

### Automated Backups to Object Storage

#### 1. Install OCI CLI

```bash
# Install OCI CLI
bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"

# Configure OCI CLI
oci setup config
```

#### 2. Create Backup Script

```bash
vim /home/trading/backup-to-oci.sh
```

```bash
#!/bin/bash
# Backup trading data to OCI Object Storage

BACKUP_DIR="/home/trading/modular_trade_agent"
BUCKET_NAME="trading-backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup trade history
oci os object put \
  --bucket-name $BUCKET_NAME \
  --file $BACKUP_DIR/data/trades_history.json \
  --name "trades_history_$DATE.json" \
  --force

# Backup analysis results
tar -czf /tmp/analysis_$DATE.tar.gz $BACKUP_DIR/analysis_results
oci os object put \
  --bucket-name $BUCKET_NAME \
  --file /tmp/analysis_$DATE.tar.gz \
  --name "analysis_$DATE.tar.gz" \
  --force

# Cleanup
rm /tmp/analysis_$DATE.tar.gz

echo "Backup completed: $DATE"
```

```bash
chmod +x /home/trading/backup-to-oci.sh
```

#### 3. Schedule Daily Backups

```bash
crontab -e
```

Add:
```
# Daily backup at 11:30 PM
30 23 * * * /home/trading/backup-to-oci.sh >> /var/log/trading/backup.log 2>&1
```

---

## Troubleshooting

### Common Issues

#### 1. Service Won't Start

```bash
# Check service status
sudo systemctl status trading-buy.service

# Check for errors
sudo journalctl -u trading-buy.service -n 50

# Verify python path
which python
/home/trading/modular_trade_agent/.venv/bin/python --version

# Test manually
cd /home/trading/modular_trade_agent
source .venv/bin/activate
python -m modules.kotak_neo_auto_trader.run_auto_trade --env modules/kotak_neo_auto_trader/kotak_neo.env
```

#### 2. Authentication Failures

```bash
# Check credentials file
cat modules/kotak_neo_auto_trader/kotak_neo.env

# Test authentication manually
python -c "
from modules.kotak_neo_auto_trader.auth import KotakNeoAuth
auth = KotakNeoAuth('modules/kotak_neo_auto_trader/kotak_neo.env')
print('Login:', auth.login())
"
```

#### 3. Timer Not Running

```bash
# Check timer is enabled
sudo systemctl is-enabled trading-buy.timer

# Check timer status
sudo systemctl status trading-buy.timer

# View next scheduled run
systemctl list-timers | grep trading

# Restart timer
sudo systemctl restart trading-buy.timer
```

#### 4. Out of Memory

```bash
# Check memory usage
free -h

# If low memory, increase swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make swap permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## Cost Optimization

### Free Tier Optimization

1. **Use ARM Instances** (A1.Flex)
   - Better performance per OCPU
   - More free resources (4 OCPU + 24 GB RAM)

2. **Optimize Storage**
   - Keep only recent logs (logrotate)
   - Archive old analysis results to Object Storage
   - Delete unused data regularly

3. **Network Optimization**
   - Free tier includes 10 TB egress/month
   - More than enough for trading bot traffic

### Monitoring Costs (If Using Paid)

```bash
# Check current costs
oci usage-api usage-summary list-summaries

# Set up budget alerts in OCI Console:
# Billing & Cost Management → Budgets → Create Budget
# Set threshold: $10/month
# Alert: Email when 80% reached
```

---

## Security Best Practices

### 1. Secure SSH Access

```bash
# Disable password authentication
sudo vim /etc/ssh/sshd_config
```

Set:
```
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
```

```bash
sudo systemctl restart sshd
```

### 2. Secure Credentials

```bash
# Ensure proper permissions
chmod 600 modules/kotak_neo_auto_trader/kotak_neo.env
chown trading:trading modules/kotak_neo_auto_trader/kotak_neo.env

# Never commit credentials to git
echo "*.env" >> .gitignore
```

### 3. Enable Automatic Security Updates

```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

### 4. Setup Fail2Ban (Optional)

```bash
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## Useful Commands Reference

### Service Management

```bash
# Start/Stop services
sudo systemctl start trading-buy.service
sudo systemctl stop trading-sell.service

# Enable/Disable timers
sudo systemctl enable trading-buy.timer
sudo systemctl disable trading-sell.timer

# View logs
sudo journalctl -u trading-buy.service -f
tail -f /var/log/trading/sell.log

# Check service status
sudo systemctl status trading-*
```

### Application Updates

```bash
# Pull latest code
cd /home/trading/modular_trade_agent
git pull origin main

# Update dependencies
source .venv/bin/activate
pip install --upgrade -r requirements.txt

# Restart services
sudo systemctl restart trading-buy.timer
sudo systemctl restart trading-sell.timer
```

### Monitoring

```bash
# System stats
htop
df -h
free -h

# Active timers
systemctl list-timers

# Recent logs
sudo journalctl -xe
```

---

## Next Steps

1. ✅ Deploy application on Oracle Cloud
2. ✅ Test manual service execution
3. ✅ Verify scheduled timers
4. ⚠️ Cancel test orders in Kotak Neo
5. 📊 Monitor first few automated runs
6. 🔔 Setup email/Telegram notifications
7. 💾 Configure automatic backups
8. 📈 Review and optimize

---

## Support & Resources

- **Oracle Cloud Docs**: [docs.oracle.com](https://docs.oracle.com/en-us/iaas/)
- **Free Tier Details**: [oracle.com/cloud/free](https://www.oracle.com/cloud/free/)
- **OCI CLI**: [docs.oracle.com/cli](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/cliconcepts.htm)
- **Kotak Neo API**: [kotaksecurities.com](https://neo.kotaksecurities.com/developer-portal)

---

**Deployment Status**: Ready for Production  
**Last Updated**: 2025-01-27  
**Platform**: Oracle Cloud Infrastructure (OCI)  
**Free Tier Compatible**: ✅ Yes
