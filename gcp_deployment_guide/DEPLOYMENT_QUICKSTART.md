# GCP Deployment - Quick Start Guide

## 🚀 Quick Deploy (5 minutes)

### Prerequisites

1. **GCP Account** with billing enabled
2. **gcloud CLI** installed ([Install Guide](https://cloud.google.com/sdk/docs/install))
3. **Kotak Neo credentials** in `modules/kotak_neo_auto_trader/kotak_neo.env`

### One-Command Deployment

```bash
# Make script executable (Linux/Mac)
chmod +x deploy-gcp.sh

# Run deployment
./deploy-gcp.sh
```

That's it! The script will:
- ✅ Enable required GCP APIs
- ✅ Store secrets securely
- ✅ Build Docker image
- ✅ Deploy Cloud Run services
- ✅ Setup Cloud Workflows
- ✅ Configure scheduler (Mon-Fri 4:00 PM IST)

## 📋 What Gets Deployed

### Analysis & Buy Orders (Cloud Run)

| Service | Schedule | Runtime | Cost/Month |
|---------|----------|---------|------------|
| **Analysis** | Mon-Fri 4:00 PM | ~30 min | ~$2-3 |
| **Buy Orders** | After analysis | ~5 min | ~$1 |

### Sell Engine (Manual Setup Required)

The sell engine runs continuously from 9:15 AM to 3:30 PM. You need to deploy it separately on Compute Engine:

```bash
# See detailed instructions in GCP_DEPLOYMENT.md
# Estimated cost: $7/month (or free with e2-micro in US regions)
```

## 🧪 Testing

### Manual Test

```bash
# Trigger workflow manually
gcloud scheduler jobs run trading-workflow-job --location=asia-south1

# Watch logs
gcloud logging tail "resource.type=cloud_run_revision"
```

### Check Status

```bash
# List services
gcloud run services list --region=asia-south1

# View scheduler jobs
gcloud scheduler jobs list --location=asia-south1

# Check workflows
gcloud workflows list --location=asia-south1
```

## 📊 Architecture

```
4:00 PM IST (Mon-Fri)
    ↓
[Cloud Scheduler]
    ↓
[Cloud Workflows] ──────┐
    ↓                   │
[Analysis Service]      │ Orchestration
    ↓                   │
[Buy Orders Service] ───┘
    ↓
[Kotak Neo API]


9:15 AM - 3:30 PM IST (Mon-Fri)
    ↓
[Sell Engine VM]
    ↓
[Monitor & Update Orders]
    ↓
[Kotak Neo API]
```

## 💰 Cost Breakdown

| Component | Type | Monthly Cost |
|-----------|------|--------------|
| Cloud Run (Analysis + Buy) | Serverless | $3-5 |
| Compute Engine (Sell) | e2-micro VM | $7 (or free in US) |
| Secret Manager | Secrets | Free (<6) |
| Cloud Storage | < 1GB | $0.02 |
| **Total** | | **~$10-12/month** |

*Can be reduced to $3-5/month by deploying VM in free tier regions*

## 🔐 Security

All credentials stored in **Secret Manager**:
- ✅ Kotak Neo API credentials
- ✅ Telegram bot token
- ✅ Never in code or logs

## 📝 Next Steps

After deployment:

1. **Deploy Sell Engine VM**
   ```bash
   # Follow instructions in GCP_DEPLOYMENT.md Section 6
   ```

2. **Setup Monitoring**
   ```bash
   # Create alert for failed jobs
   gcloud alpha monitoring policies create --display-name="Trading Failures"
   ```

3. **Test End-to-End**
   ```bash
   # Run analysis manually
   gcloud scheduler jobs run trading-workflow-job --location=asia-south1
   
   # Check results
   gcloud run services logs read trading-analysis --limit=100
   ```

4. **Review Logs**
   - Analysis: Check for stock recommendations
   - Buy Orders: Verify orders placed
   - Sell Engine: Monitor order updates

## 🛠️ Maintenance

### Update Code

```bash
# Push new Docker image
gcloud builds submit --tag gcr.io/$PROJECT_ID/trading-agent

# Update services
gcloud run services update trading-analysis \
    --image gcr.io/$PROJECT_ID/trading-agent

gcloud run services update trading-buy-orders \
    --image gcr.io/$PROJECT_ID/trading-agent
```

### Update Secrets

```bash
# Update Kotak credentials
gcloud secrets versions add kotak-neo-env \
    --data-file=modules/kotak_neo_auto_trader/kotak_neo.env
```

### Check Costs

```bash
# View current month billing
gcloud billing projects describe $PROJECT_ID --format=json
```

## ⚠️ Important Notes

1. **Market Hours**: Sell engine only operates 9:15 AM - 3:30 PM IST
2. **Weekends**: All jobs skip weekends automatically
3. **Holidays**: Need to manually pause on market holidays
4. **2FA**: Kotak Neo requires MPIN for authentication
5. **Rate Limits**: Be aware of Kotak API rate limits

## 🐛 Troubleshooting

### Jobs Not Running

```bash
# Check scheduler status
gcloud scheduler jobs describe trading-workflow-job --location=asia-south1

# View execution history
gcloud workflows executions list trading-workflow --location=asia-south1
```

### Service Errors

```bash
# View service logs
gcloud run services logs read trading-analysis --limit=50

# Check service configuration
gcloud run services describe trading-analysis --region=asia-south1
```

### VM Issues

```bash
# SSH into VM
gcloud compute ssh trading-sell-engine --zone=asia-south1-a

# Check service status
sudo systemctl status sell-engine

# View logs
sudo journalctl -u sell-engine -f
```

## 📚 Documentation

- **Complete Guide**: [GCP_DEPLOYMENT.md](GCP_DEPLOYMENT.md)
- **Parallel Monitoring**: [PARALLEL_MONITORING.md](modules/kotak_neo_auto_trader/PARALLEL_MONITORING.md)
- **Scrip Master**: [BUY_SCRIP_MASTER.md](modules/kotak_neo_auto_trader/BUY_SCRIP_MASTER.md)
- **Sell Orders**: [SELL_ORDERS_README.md](modules/kotak_neo_auto_trader/SELL_ORDERS_README.md)

## 🆘 Support

If you encounter issues:

1. Check logs: `gcloud logging tail`
2. Review [GCP_DEPLOYMENT.md](GCP_DEPLOYMENT.md) troubleshooting section
3. Verify secrets are accessible
4. Ensure Kotak Neo credentials are valid
5. Check market hours and holidays

## ✅ Pre-Deployment Checklist

- [ ] GCP account with billing
- [ ] gcloud CLI installed and authenticated
- [ ] Kotak Neo credentials in `kotak_neo.env`
- [ ] Telegram bot token (optional)
- [ ] Project ID selected
- [ ] Region selected (recommend: asia-south1)
- [ ] Understand costs (~$10-12/month)

Ready to deploy? Run `./deploy-gcp.sh`! 🚀
