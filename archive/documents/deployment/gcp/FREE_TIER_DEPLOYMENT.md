# Google Cloud Free Tier Deployment - Trading Agent

## 🎉 Run Your Trading System for FREE (or under $5/month)

This guide optimizes your deployment to maximize Google Cloud's generous Free Tier.

## 📊 Google Cloud Free Tier Limits (Always Free)

### Compute Engine
- ✅ **1 e2-micro VM** in us-central1, us-west1, us-east1
- ✅ **30 GB standard persistent disk**
- ✅ **1 GB egress per month**

### Cloud Run
- ✅ **2 million requests/month**
- ✅ **360,000 GB-seconds CPU**
- ✅ **180,000 vCPU-seconds**
- ✅ **1 GB outbound data transfer**

### Cloud Storage
- ✅ **5 GB storage**
- ✅ **5,000 Class A operations**
- ✅ **50,000 Class B operations**

### Secret Manager
- ✅ **6 active secret versions** (free forever)

### Other Services
- ✅ Cloud Logging: 50 GB/month
- ✅ Cloud Monitoring: Free metrics
- ✅ Cloud Scheduler: 3 jobs free

## 💰 Cost Breakdown: Free Tier Optimized

| Component | Usage | Free Tier | Monthly Cost |
|-----------|-------|-----------|--------------|
| **Compute Engine** (e2-micro VM) | 24/7 in us-central1 | ✅ FREE | $0 |
| **Cloud Run** (Analysis) | 22 runs × 30 min | ✅ Within limits | $0 |
| **Cloud Run** (Buy Orders) | 22 runs × 5 min | ✅ Within limits | $0 |
| **Cloud Storage** | < 1 GB | ✅ Within limits | $0 |
| **Secret Manager** | 2 secrets × 1 version | ✅ Within limits | $0 |
| **Cloud Scheduler** | 2 jobs | ✅ Within limits | $0 |
| **Networking** | < 1 GB/month | ✅ Within limits | $0 |
| **TOTAL** | | | **$0/month** 🎉 |

## 🚀 Free Tier Deployment Strategy

### Option 1: All-on-VM (100% FREE)

Run everything on the free e2-micro VM:

**Pros:**
- ✅ Completely FREE
- ✅ No time limits
- ✅ Simple architecture

**Cons:**
- ⚠️ Must be in us-central1, us-west1, or us-east1
- ⚠️ Limited to 1GB RAM
- ⚠️ Need to manage cron jobs manually

### Option 2: Hybrid (Recommended, ~$0-3/month)

- **VM**: Free e2-micro for sell engine
- **Cloud Run**: For analysis & buy orders (within free tier limits)

**Pros:**
- ✅ Mostly FREE
- ✅ Better separation of concerns
- ✅ Cloud Scheduler automation
- ✅ Easier monitoring

**Cons:**
- ⚠️ May exceed free tier if analysis takes >30 min frequently
- ⚠️ ~$0-3/month if you slightly exceed limits

## 📝 Free Tier Deployment Steps

### Step 1: Choose Free Tier Region

**IMPORTANT:** For FREE e2-micro, use one of these regions:
- `us-central1` (Iowa)
- `us-west1` (Oregon)
- `us-east1` (South Carolina)

```bash
export REGION="us-central1"
export ZONE="us-central1-a"
```

### Step 2: Deploy VM (FREE e2-micro)

```bash
# Create free tier VM
gcloud compute instances create trading-system \
    --zone=$ZONE \
    --machine-type=e2-micro \
    --boot-disk-size=30GB \
    --boot-disk-type=pd-standard \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --scopes=cloud-platform \
    --tags=trading-system \
    --metadata=startup-script='#!/bin/bash
apt-get update
apt-get install -y python3.12 python3-pip git cron

# Clone repository
cd /opt
git clone https://github.com/your-repo/modular_trade_agent.git
cd modular_trade_agent

# Install requirements
pip3 install -r requirements.txt

# Get secrets from Secret Manager
gcloud secrets versions access latest --secret="kotak-neo-env" > modules/kotak_neo_auto_trader/kotak_neo.env
gcloud secrets versions access latest --secret="telegram-config" > config/.env

# Setup cron jobs
cat > /etc/cron.d/trading-system << EOF
# Analysis and buy orders (Mon-Fri 4:00 PM IST = 10:30 AM UTC)
30 10 * * 1-5 root cd /opt/modular_trade_agent && /usr/bin/python3 -m src.presentation.cli.application analyze --backtest && /usr/bin/python3 -m modules.kotak_neo_auto_trader.run_auto_trade --env modules/kotak_neo_auto_trader/kotak_neo.env

# Sell engine (Mon-Fri 9:15 AM IST = 3:45 AM UTC, runs until 3:30 PM IST)
45 3 * * 1-5 root cd /opt/modular_trade_agent && /usr/bin/python3 -m modules.kotak_neo_auto_trader.run_sell_orders
EOF

chmod 644 /etc/cron.d/trading-system
'
```

### Step 3: Setup Monitoring (FREE)

```bash
# Install monitoring agent (optional, but free)
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install
```

### Step 4: Configure Alerts (FREE)

```bash
# Create email notification channel
gcloud alpha monitoring channels create \
    --display-name="Trading Alerts Email" \
    --type=email \
    --channel-labels=email_address=your-email@example.com

# Create uptime check (free)
gcloud monitoring uptime create http trading-vm-check \
    --resource-type=uptime-url \
    --host=metadata.google.internal \
    --path=/
```

## 🔄 Alternative: Cloud Run + Free VM Hybrid

If you prefer Cloud Scheduler automation but want to stay free:

### Deploy Cloud Run (Stays within free tier)

```bash
# Use default region (any region works for Cloud Run free tier)
export REGION="us-central1"

# Build image (Cloud Build free tier: 120 build-minutes/day)
gcloud builds submit --tag gcr.io/$PROJECT_ID/trading-agent

# Deploy analysis (within free tier: 360K GB-seconds/month)
gcloud run deploy trading-analysis \
    --image gcr.io/$PROJECT_ID/trading-agent \
    --region $REGION \
    --memory 512Mi \
    --cpu 1 \
    --timeout 30m \
    --max-instances 1 \
    --no-allow-unauthenticated \
    --set-secrets="/app/modules/kotak_neo_auto_trader/kotak_neo.env=kotak-neo-env:latest" \
    --set-secrets="TELEGRAM_BOT_TOKEN=telegram-config:latest:TELEGRAM_BOT_TOKEN" \
    --set-secrets="TELEGRAM_CHAT_ID=telegram-config:latest:TELEGRAM_CHAT_ID" \
    --command "python,-m,src.presentation.cli.application,analyze,--backtest"

# Deploy buy orders (minimal usage)
gcloud run deploy trading-buy-orders \
    --image gcr.io/$PROJECT_ID/trading-agent \
    --region $REGION \
    --memory 512Mi \
    --cpu 1 \
    --timeout 10m \
    --max-instances 1 \
    --no-allow-unauthenticated \
    --set-secrets="/app/modules/kotak_neo_auto_trader/kotak_neo.env=kotak-neo-env:latest" \
    --set-secrets="TELEGRAM_BOT_TOKEN=telegram-config:latest:TELEGRAM_BOT_TOKEN" \
    --set-secrets="TELEGRAM_CHAT_ID=telegram-config:latest:TELEGRAM_CHAT_ID" \
    --command "python,-m,modules.kotak_neo_auto_trader.run_auto_trade,--env,modules/kotak_neo_auto_trader/kotak_neo.env"
```

### Optimize for Free Tier

```bash
# Reduce memory and CPU to minimize charges
# Analysis: 512MB × 30 min × 22 days = ~330 GB-seconds (well within 360K limit)
# Buy Orders: 512MB × 5 min × 22 days = ~55 GB-seconds

# Setup Cloud Scheduler (3 jobs free)
gcloud scheduler jobs create http trading-workflow-job \
    --location=$REGION \
    --schedule="30 10 * * 1-5" \
    --time-zone="UTC" \
    --uri="https://trading-analysis-xxxxx.run.app" \
    --http-method=POST \
    --oidc-service-account-email="trading-scheduler@$PROJECT_ID.iam.gserviceaccount.com"
```

## 💡 Free Tier Optimization Tips

### 1. Reduce Cloud Run Memory

```bash
# Use minimal memory (saves GB-seconds)
--memory 512Mi  # Instead of 2Gi
```

### 2. Limit Max Instances

```bash
# Prevent accidental scaling
--max-instances 1
```

### 3. Use Standard Disk (Not SSD)

```bash
# Free tier includes standard persistent disk
--boot-disk-type=pd-standard  # NOT pd-ssd
```

### 4. Keep VM in Free Tier Regions

```bash
# MUST use one of these for free e2-micro
us-central1-a
us-central1-b
us-central1-c
us-central1-f
us-west1-a
us-west1-b
us-west1-c
us-east1-b
us-east1-c
us-east1-d
```

### 5. Monitor Free Tier Usage

```bash
# Check current usage
gcloud billing projects describe $PROJECT_ID

# View detailed billing
gcloud alpha billing accounts describe $BILLING_ACCOUNT --format=json
```

### 6. Set Budget Alerts

```bash
# Set $1 budget alert (optional safety net)
gcloud billing budgets create \
    --billing-account=$BILLING_ACCOUNT \
    --display-name="Trading System Budget" \
    --budget-amount=1.00 \
    --threshold-rule=percent=50 \
    --threshold-rule=percent=90 \
    --threshold-rule=percent=100
```

## 📊 Free Tier Usage Calculator

### Monthly Usage Estimate

**Cloud Run (Analysis):**
```
Memory: 512 MB = 0.5 GB
Time: 30 min = 1800 seconds
Runs: 22 days/month
Total: 0.5 GB × 1800 sec × 22 = 19,800 GB-seconds
Free Tier: 360,000 GB-seconds
Usage: 5.5% ✅
```

**Cloud Run (Buy Orders):**
```
Memory: 512 MB = 0.5 GB
Time: 5 min = 300 seconds
Runs: 22 days/month
Total: 0.5 GB × 300 sec × 22 = 3,300 GB-seconds
Usage: 0.9% ✅
```

**Total Cloud Run Usage: 23,100 GB-seconds (6.4% of free tier)** ✅

## 🚨 Staying Within Free Tier

### What's Covered FREE:

✅ 1 e2-micro VM (24/7 in specified regions)
✅ Analysis + Buy orders via Cloud Run
✅ Sell engine on VM
✅ Secret Manager (up to 6 secrets)
✅ Cloud Storage (up to 5 GB)
✅ Cloud Scheduler (up to 3 jobs)
✅ Monitoring and logging
✅ Telegram notifications (Telegram is free)

### What Might Cost Extra:

⚠️ If analysis takes > 30 min regularly
⚠️ If you use >30 GB disk
⚠️ If egress exceeds 1 GB/month
⚠️ If you deploy in non-free-tier regions

**Expected Cost: $0-3/month if you slightly exceed**

## 🎯 Recommended Free Tier Setup

```bash
#!/bin/bash
# free-tier-deploy.sh

PROJECT_ID="your-project-id"
REGION="us-central1"
ZONE="us-central1-a"

# Deploy everything on free e2-micro VM
gcloud compute instances create trading-system \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --machine-type=e2-micro \
    --boot-disk-size=30GB \
    --boot-disk-type=pd-standard \
    --scopes=cloud-platform \
    --metadata-from-file=startup-script=startup-free-tier.sh

echo "✅ Free tier deployment complete!"
echo "Cost: $0/month"
echo "VM will handle all tasks via cron jobs"
```

## 📝 Maintenance on Free Tier

### Update Application

```bash
# SSH into VM
gcloud compute ssh trading-system --zone=$ZONE

# Pull latest code
cd /opt/modular_trade_agent
git pull

# Restart if using systemd services
sudo systemctl restart trading-*
```

### View Logs

```bash
# SSH and check logs
gcloud compute ssh trading-system --zone=$ZONE
sudo journalctl -u cron -f
```

### Monitor Costs

```bash
# Check you're still in free tier
gcloud billing projects describe $PROJECT_ID

# View usage dashboard
echo "Visit: https://console.cloud.google.com/billing"
```

## ✅ Free Tier Checklist

- [ ] Project in free trial or billing enabled
- [ ] VM in us-central1, us-west1, or us-east1
- [ ] Machine type: e2-micro
- [ ] Disk size: ≤ 30 GB standard
- [ ] Cloud Run memory: ≤ 512 MB
- [ ] Cloud Run instances: max 1
- [ ] Secrets: ≤ 6 active versions
- [ ] Budget alert set (optional)

## 🎉 Result

**Total Monthly Cost: $0** 🎊

Your entire trading system runs completely FREE on Google Cloud!

## 📚 Related

- **Full GCP Guide**: [GCP_DEPLOYMENT.md](GCP_DEPLOYMENT.md)
- **Quick Start**: [DEPLOYMENT_QUICKSTART.md](DEPLOYMENT_QUICKSTART.md)
- **Telegram Setup**: [TELEGRAM_GCP_SETUP.md](TELEGRAM_GCP_SETUP.md)
