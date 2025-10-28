# GCP Deployment Guide - Automated Trading System

## Overview

This guide covers deploying the end-to-end automated trading system on Google Cloud Platform with proper scheduling and monitoring.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        GCP Cloud                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Cloud Scheduler (Cron Jobs)                         │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  1. Analysis Job: Mon-Fri @ 4:00 PM IST             │  │
│  │  2. Buy Orders: Mon-Fri @ 4:00 PM IST (after #1)    │  │
│  │  3. Sell Engine: Mon-Fri @ 9:15 AM - 3:30 PM IST    │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Cloud Run / Compute Engine                          │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  - Python runtime environment                        │  │
│  │  - Docker containerized application                  │  │
│  │  - Secret Manager for credentials                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Cloud Storage / Firestore                           │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  - Trade history                                     │  │
│  │  - Analysis results                                  │  │
│  │  - Scrip master cache                                │  │
│  │  - Logs and monitoring data                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
                  Kotak Neo API
```

## Deployment Options

### Option 1: Cloud Run (Recommended)
**Pros:**
- Serverless, pay-per-use
- Auto-scaling
- Easy deployment
- No infrastructure management

**Cons:**
- 60-minute execution limit (need to handle long-running sell engine)
- Cold start delays

### Option 2: Compute Engine VM
**Pros:**
- Full control
- No execution time limits
- Can run continuously
- Better for long-running processes

**Cons:**
- More expensive (always-on)
- Requires manual scaling
- Need to manage OS updates

**Recommendation:** Use **Compute Engine e2-micro** (always free tier eligible) for continuous sell engine monitoring.

## Step-by-Step Deployment

### 1. Prepare Application

#### Create Dockerfile

```dockerfile
# Dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set Python path
ENV PYTHONPATH=/app

# Default command (will be overridden by Cloud Scheduler)
CMD ["python", "-m", "src.presentation.cli.application", "analyze", "--backtest"]
```

#### Create .dockerignore

```
# .dockerignore
.git
.venv
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.log
.env
*.env
!kotak_neo.env
.DS_Store
.pytest_cache
.coverage
htmlcov/
dist/
build/
*.egg-info/
```

### 2. Setup GCP Project

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
export REGION="asia-south1"  # Mumbai region for lower latency

# Enable required APIs
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    secretmanager.googleapis.com \
    compute.googleapis.com

# Authenticate
gcloud auth login
gcloud config set project $PROJECT_ID
```

### 3. Store Secrets

```bash
# Store Kotak Neo credentials in Secret Manager
gcloud secrets create kotak-neo-env \
    --data-file=modules/kotak_neo_auto_trader/kotak_neo.env

# Store Telegram credentials
gcloud secrets create telegram-config \
    --data-file=config/.env

# Grant access to compute service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding kotak-neo-env \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### 4. Create Docker Image

```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/$PROJECT_ID/trading-agent

# Or use Artifact Registry (recommended)
gcloud artifacts repositories create trading-agent \
    --repository-format=docker \
    --location=$REGION

gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/trading-agent/app:latest
```

### 5. Deploy Analysis & Buy Order Job (Cloud Run)

#### Create Cloud Run service for analysis

```bash
# Deploy analysis service
gcloud run deploy trading-analysis \
    --image gcr.io/$PROJECT_ID/trading-agent \
    --region $REGION \
    --memory 2Gi \
    --timeout 30m \
    --no-allow-unauthenticated \
    --set-secrets="/app/modules/kotak_neo_auto_trader/kotak_neo.env=kotak-neo-env:latest" \
    --set-secrets="/app/config/.env=telegram-config:latest" \
    --command "python,-m,src.presentation.cli.application,analyze,--backtest"
```

#### Create Cloud Run service for buy orders

```bash
# Deploy buy orders service
gcloud run deploy trading-buy-orders \
    --image gcr.io/$PROJECT_ID/trading-agent \
    --region $REGION \
    --memory 1Gi \
    --timeout 10m \
    --no-allow-unauthenticated \
    --set-secrets="/app/modules/kotak_neo_auto_trader/kotak_neo.env=kotak-neo-env:latest" \
    --command "python,-m,modules.kotak_neo_auto_trader.run_auto_trade,--env,modules/kotak_neo_auto_trader/kotak_neo.env"
```

### 6. Deploy Sell Engine (Compute Engine)

#### Create startup script

```bash
# create-sell-engine-vm.sh
cat > startup-script.sh << 'EOF'
#!/bin/bash

# Install Python and dependencies
apt-get update
apt-get install -y python3.12 python3-pip git

# Clone repository (or copy from Cloud Storage)
cd /opt
git clone https://github.com/your-repo/modular_trade_agent.git
cd modular_trade_agent

# Install requirements
pip3 install -r requirements.txt

# Get secrets from Secret Manager
gcloud secrets versions access latest --secret="kotak-neo-env" > modules/kotak_neo_auto_trader/kotak_neo.env
gcloud secrets versions access latest --secret="telegram-config" > config/.env

# Create systemd service for sell engine
cat > /etc/systemd/system/sell-engine.service << 'SERVICE'
[Unit]
Description=Trading Sell Engine
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/modular_trade_agent
Environment="PYTHONPATH=/opt/modular_trade_agent"
ExecStart=/usr/bin/python3 -m modules.kotak_neo_auto_trader.run_sell_orders
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
SERVICE

# Enable and start service
systemctl daemon-reload
systemctl enable sell-engine
systemctl start sell-engine
EOF
```

#### Create VM

```bash
# Create VM for sell engine
gcloud compute instances create trading-sell-engine \
    --zone=asia-south1-a \
    --machine-type=e2-micro \
    --boot-disk-size=20GB \
    --boot-disk-type=pd-standard \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --metadata-from-file=startup-script=startup-script.sh \
    --scopes=cloud-platform \
    --tags=trading-sell-engine
```

### 7. Setup Cloud Scheduler

#### Job 1: Daily Analysis (4:00 PM IST)

```bash
# Create service account for scheduler
gcloud iam service-accounts create trading-scheduler \
    --display-name="Trading System Scheduler"

# Grant invoker role
gcloud run services add-iam-policy-binding trading-analysis \
    --member="serviceAccount:trading-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region=$REGION

# Create scheduler job
gcloud scheduler jobs create http analysis-job \
    --location=$REGION \
    --schedule="0 16 * * 1-5" \
    --time-zone="Asia/Kolkata" \
    --uri="https://trading-analysis-xxxxx.run.app" \
    --http-method=POST \
    --oidc-service-account-email="trading-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --oidc-token-audience="https://trading-analysis-xxxxx.run.app"
```

#### Job 2: Place Buy Orders (4:30 PM IST, after analysis)

```bash
# Grant invoker role
gcloud run services add-iam-policy-binding trading-buy-orders \
    --member="serviceAccount:trading-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region=$REGION

# Create scheduler job
gcloud scheduler jobs create http buy-orders-job \
    --location=$REGION \
    --schedule="30 16 * * 1-5" \
    --time-zone="Asia/Kolkata" \
    --uri="https://trading-buy-orders-xxxxx.run.app" \
    --http-method=POST \
    --oidc-service-account-email="trading-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --oidc-token-audience="https://trading-buy-orders-xxxxx.run.app"
```

#### Job 3: Start Sell Engine (9:15 AM IST)

```bash
# Note: Sell engine runs continuously on VM, no scheduler needed
# VM will auto-start the service and it will check market hours internally
```

## Workflow Orchestration with Cloud Workflows

For better coordination between analysis and buy orders, use Cloud Workflows:

```yaml
# workflow.yaml
main:
  steps:
    - analyze:
        call: http.post
        args:
          url: https://trading-analysis-xxxxx.run.app
          auth:
            type: OIDC
        result: analysis_result
    
    - check_analysis:
        switch:
          - condition: ${analysis_result.code == 200}
            next: place_orders
        next: end
    
    - place_orders:
        call: http.post
        args:
          url: https://trading-buy-orders-xxxxx.run.app
          auth:
            type: OIDC
        result: buy_result
    
    - end:
        return: ${buy_result}
```

Deploy workflow:

```bash
gcloud workflows deploy trading-workflow \
    --source=workflow.yaml \
    --location=$REGION

# Update scheduler to trigger workflow instead
gcloud scheduler jobs create http trading-workflow-job \
    --location=$REGION \
    --schedule="0 16 * * 1-5" \
    --time-zone="Asia/Kolkata" \
    --uri="https://workflowexecutions.googleapis.com/v1/projects/$PROJECT_ID/locations/$REGION/workflows/trading-workflow/executions" \
    --http-method=POST \
    --oauth-service-account-email="trading-scheduler@$PROJECT_ID.iam.gserviceaccount.com"
```

## Monitoring and Alerting

### Setup Cloud Monitoring

```bash
# Create notification channel (email)
gcloud alpha monitoring channels create \
    --display-name="Trading Alerts" \
    --type=email \
    --channel-labels=email_address=your-email@example.com

# Create alert policy for failed jobs
gcloud alpha monitoring policies create \
    --display-name="Trading Job Failed" \
    --condition-display-name="Job Failure" \
    --condition-threshold-value=1 \
    --condition-threshold-duration=60s
```

### Setup Logging

```bash
# Create log sink for trade history
gcloud logging sinks create trading-logs \
    gs://your-bucket/trading-logs \
    --log-filter='resource.type="cloud_run_revision" AND resource.labels.service_name=~"trading-"'
```

## Cost Estimation

### Cloud Run (Analysis + Buy Orders)
- **Analysis:** 30 min/day × 22 days = 11 hours/month
- **Buy Orders:** 5 min/day × 22 days = 1.8 hours/month
- **Cost:** ~$2-5/month

### Compute Engine (Sell Engine)
- **VM:** e2-micro always-on = ~$7/month
- **Free tier eligible:** First 720 hours/month free in us-central1, us-west1, us-east1
- **Cost in asia-south1:** ~$7/month

### Storage
- **Cloud Storage:** <1GB = ~$0.02/month
- **Secret Manager:** Free for <6 secrets

**Total Estimated Cost:** ~$7-12/month (or ~$0 if using free tier in US regions)

## Deployment Checklist

- [ ] Create GCP project
- [ ] Enable required APIs
- [ ] Store secrets in Secret Manager
- [ ] Build and push Docker image
- [ ] Deploy Cloud Run services
- [ ] Create Compute Engine VM for sell engine
- [ ] Setup Cloud Scheduler jobs
- [ ] Configure monitoring and alerts
- [ ] Test end-to-end workflow
- [ ] Setup backup and disaster recovery
- [ ] Document runbooks for common issues

## Testing

### Test Analysis Job

```bash
# Trigger manually
gcloud scheduler jobs run analysis-job --location=$REGION

# Check logs
gcloud run services logs read trading-analysis --region=$REGION --limit=100
```

### Test Buy Orders

```bash
# Trigger manually
gcloud scheduler jobs run buy-orders-job --location=$REGION

# Check logs
gcloud run services logs read trading-buy-orders --region=$REGION --limit=100
```

### Test Sell Engine

```bash
# SSH into VM
gcloud compute ssh trading-sell-engine --zone=asia-south1-a

# Check service status
sudo systemctl status sell-engine

# View logs
sudo journalctl -u sell-engine -f
```

## Maintenance

### Update Application

```bash
# Rebuild image
gcloud builds submit --tag gcr.io/$PROJECT_ID/trading-agent

# Update Cloud Run services
gcloud run services update trading-analysis --image gcr.io/$PROJECT_ID/trading-agent --region=$REGION
gcloud run services update trading-buy-orders --image gcr.io/$PROJECT_ID/trading-agent --region=$REGION

# Update VM (SSH and pull latest code)
gcloud compute ssh trading-sell-engine --zone=asia-south1-a
cd /opt/modular_trade_agent
git pull
sudo systemctl restart sell-engine
```

### Backup Strategy

```bash
# Daily backup of trade history to Cloud Storage
gcloud scheduler jobs create app-engine backup-trades \
    --schedule="0 23 * * *" \
    --time-zone="Asia/Kolkata" \
    --relative-url="/backup" \
    --http-method=GET
```

## Troubleshooting

### Issue: Jobs not triggering
**Check:**
1. Cloud Scheduler enabled
2. Service account has invoker permissions
3. Time zone set correctly (Asia/Kolkata)

### Issue: Sell engine not running
**Check:**
1. VM is running: `gcloud compute instances list`
2. Service status: `sudo systemctl status sell-engine`
3. Check logs: `sudo journalctl -u sell-engine -n 100`

### Issue: Out of memory
**Solution:**
- Increase Cloud Run memory allocation
- Optimize data processing
- Use streaming instead of loading all data

## Security Best Practices

1. **Never commit credentials** - Use Secret Manager
2. **Restrict IAM permissions** - Principle of least privilege
3. **Enable VPC Service Controls** - For additional security
4. **Regular security audits** - Review access logs
5. **Enable audit logging** - Track all API calls
6. **Use private IPs** - For VM communication
7. **Encrypt at rest** - Enable encryption for storage

## Next Steps

1. Setup CI/CD with Cloud Build
2. Implement automated testing
3. Add health checks and monitoring
4. Setup disaster recovery
5. Create runbooks for operations
6. Implement feature flags for safe deployments

## Related Files

- `Dockerfile` - Container definition
- `requirements.txt` - Python dependencies
- `.dockerignore` - Files to exclude from image
- `workflow.yaml` - Cloud Workflows definition
- `startup-script.sh` - VM initialization script
