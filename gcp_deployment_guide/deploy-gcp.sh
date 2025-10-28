#!/bin/bash
# Quick GCP Deployment Script for Trading Agent
# Usage: ./deploy-gcp.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Trading Agent - GCP Deployment${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI not found. Please install it first.${NC}"
    exit 1
fi

# Get project configuration
echo -e "\n${YELLOW}Step 1: Configuration${NC}"
read -p "Enter your GCP Project ID: " PROJECT_ID
read -p "Enter region (default: asia-south1): " REGION
REGION=${REGION:-asia-south1}

export PROJECT_ID
export REGION

echo -e "${GREEN}✓ Using Project: $PROJECT_ID${NC}"
echo -e "${GREEN}✓ Using Region: $REGION${NC}"

# Set project
gcloud config set project $PROJECT_ID

# Enable APIs
echo -e "\n${YELLOW}Step 2: Enabling Required APIs${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    secretmanager.googleapis.com \
    compute.googleapis.com \
    workflows.googleapis.com

echo -e "${GREEN}✓ APIs enabled${NC}"

# Store secrets
echo -e "\n${YELLOW}Step 3: Storing Secrets${NC}"
if [ -f "modules/kotak_neo_auto_trader/kotak_neo.env" ]; then
    gcloud secrets create kotak-neo-env --data-file=modules/kotak_neo_auto_trader/kotak_neo.env 2>/dev/null || \
    gcloud secrets versions add kotak-neo-env --data-file=modules/kotak_neo_auto_trader/kotak_neo.env
    echo -e "${GREEN}✓ Kotak Neo credentials stored${NC}"
else
    echo -e "${RED}✗ kotak_neo.env not found${NC}"
fi

if [ -f "config/.env" ]; then
    gcloud secrets create telegram-config --data-file=config/.env 2>/dev/null || \
    gcloud secrets versions add telegram-config --data-file=config/.env
    echo -e "${GREEN}✓ Telegram config stored${NC}"
else
    echo -e "${YELLOW}⚠ config/.env not found (optional)${NC}"
fi

# Grant secret access
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding kotak-neo-env \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" > /dev/null

# Build Docker image
echo -e "\n${YELLOW}Step 4: Building Docker Image${NC}"
gcloud builds submit --tag gcr.io/$PROJECT_ID/trading-agent
echo -e "${GREEN}✓ Docker image built${NC}"

# Deploy Cloud Run services
echo -e "\n${YELLOW}Step 5: Deploying Cloud Run Services${NC}"

# Analysis service
echo "Deploying analysis service..."
gcloud run deploy trading-analysis \
    --image gcr.io/$PROJECT_ID/trading-agent \
    --region $REGION \
    --memory 2Gi \
    --timeout 30m \
    --no-allow-unauthenticated \
    --set-secrets="/app/modules/kotak_neo_auto_trader/kotak_neo.env=kotak-neo-env:latest" \
    --set-secrets="TELEGRAM_BOT_TOKEN=telegram-config:latest:TELEGRAM_BOT_TOKEN" \
    --set-secrets="TELEGRAM_CHAT_ID=telegram-config:latest:TELEGRAM_CHAT_ID" \
    --command "python,-m,src.presentation.cli.application,analyze,--backtest" \
    --quiet

ANALYSIS_URL=$(gcloud run services describe trading-analysis --region=$REGION --format='value(status.url)')
echo -e "${GREEN}✓ Analysis service deployed: $ANALYSIS_URL${NC}"

# Buy orders service
echo "Deploying buy orders service..."
gcloud run deploy trading-buy-orders \
    --image gcr.io/$PROJECT_ID/trading-agent \
    --region $REGION \
    --memory 1Gi \
    --timeout 10m \
    --no-allow-unauthenticated \
    --set-secrets="/app/modules/kotak_neo_auto_trader/kotak_neo.env=kotak-neo-env:latest" \
    --set-secrets="TELEGRAM_BOT_TOKEN=telegram-config:latest:TELEGRAM_BOT_TOKEN" \
    --set-secrets="TELEGRAM_CHAT_ID=telegram-config:latest:TELEGRAM_CHAT_ID" \
    --command "python,-m,modules.kotak_neo_auto_trader.run_auto_trade,--env,modules/kotak_neo_auto_trader/kotak_neo.env" \
    --quiet

BUY_ORDERS_URL=$(gcloud run services describe trading-buy-orders --region=$REGION --format='value(status.url)')
echo -e "${GREEN}✓ Buy orders service deployed: $BUY_ORDERS_URL${NC}"

# Create service account for scheduler
echo -e "\n${YELLOW}Step 6: Setting up Cloud Scheduler${NC}"
gcloud iam service-accounts create trading-scheduler \
    --display-name="Trading System Scheduler" 2>/dev/null || echo "Service account already exists"

# Grant invoker permissions
gcloud run services add-iam-policy-binding trading-analysis \
    --member="serviceAccount:trading-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region=$REGION \
    --quiet

gcloud run services add-iam-policy-binding trading-buy-orders \
    --member="serviceAccount:trading-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region=$REGION \
    --quiet

# Create Cloud Workflows
echo "Deploying workflow..."
# Update workflow.yaml with actual URLs
sed "s|analysis_url: \"\"|analysis_url: \"$ANALYSIS_URL\"|g" workflow.yaml | \
sed "s|buy_orders_url: \"\"|buy_orders_url: \"$BUY_ORDERS_URL\"|g" > workflow-temp.yaml

gcloud workflows deploy trading-workflow \
    --source=workflow-temp.yaml \
    --location=$REGION \
    --quiet

rm workflow-temp.yaml
echo -e "${GREEN}✓ Workflow deployed${NC}"

# Create scheduler job for workflow
gcloud scheduler jobs delete trading-workflow-job --location=$REGION --quiet 2>/dev/null || true
gcloud scheduler jobs create http trading-workflow-job \
    --location=$REGION \
    --schedule="0 16 * * 1-5" \
    --time-zone="Asia/Kolkata" \
    --uri="https://workflowexecutions.googleapis.com/v1/projects/$PROJECT_ID/locations/$REGION/workflows/trading-workflow/executions" \
    --http-method=POST \
    --oauth-service-account-email="trading-scheduler@$PROJECT_ID.iam.gserviceaccount.com" \
    --quiet

echo -e "${GREEN}✓ Scheduler configured (Mon-Fri 4:00 PM IST)${NC}"

# Summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\n${YELLOW}Services deployed:${NC}"
echo -e "  Analysis:    $ANALYSIS_URL"
echo -e "  Buy Orders:  $BUY_ORDERS_URL"
echo -e "\n${YELLOW}Scheduled jobs:${NC}"
echo -e "  Workflow: Mon-Fri @ 4:00 PM IST"
echo -e "\n${YELLOW}Next steps:${NC}"
echo -e "  1. Deploy sell engine VM (see GCP_DEPLOYMENT.md)"
echo -e "  2. Test manually: gcloud scheduler jobs run trading-workflow-job --location=$REGION"
echo -e "  3. Monitor logs: gcloud logging read 'resource.type=\"cloud_run_revision\"' --limit 50"
echo -e "\n${GREEN}========================================${NC}"
