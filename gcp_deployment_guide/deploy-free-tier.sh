#!/bin/bash
# Free Tier Deployment Script - $0/month Trading System
# Usage: ./deploy-free-tier.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Trading Agent - FREE TIER Deployment${NC}"
echo -e "${GREEN}Cost: \$0/month 🎉${NC}"
echo -e "${GREEN}========================================${NC}"

# Configuration
read -p "Enter your GCP Project ID: " PROJECT_ID
echo -e "${YELLOW}Choose a FREE TIER region:${NC}"
echo "1. us-central1 (Iowa)"
echo "2. us-west1 (Oregon)"
echo "3. us-east1 (South Carolina)"
read -p "Enter choice [1-3]: " REGION_CHOICE

case $REGION_CHOICE in
    1) REGION="us-central1"; ZONE="us-central1-a" ;;
    2) REGION="us-west1"; ZONE="us-west1-a" ;;
    3) REGION="us-east1"; ZONE="us-east1-b" ;;
    *) echo "Invalid choice"; exit 1 ;;
esac

echo -e "${GREEN}✓ Using Region: $REGION (FREE TIER)${NC}"

gcloud config set project $PROJECT_ID

# Enable APIs
echo -e "\n${YELLOW}Enabling APIs...${NC}"
gcloud services enable \
    compute.googleapis.com \
    secretmanager.googleapis.com \
    logging.googleapis.com

# Store secrets
echo -e "\n${YELLOW}Storing secrets...${NC}"
if [ -f "modules/kotak_neo_auto_trader/kotak_neo.env" ]; then
    gcloud secrets create kotak-neo-env --data-file=modules/kotak_neo_auto_trader/kotak_neo.env 2>/dev/null || \
    gcloud secrets versions add kotak-neo-env --data-file=modules/kotak_neo_auto_trader/kotak_neo.env
    echo -e "${GREEN}✓ Kotak credentials stored${NC}"
fi

if [ -f "config/.env" ]; then
    gcloud secrets create telegram-config --data-file=config/.env 2>/dev/null || \
    gcloud secrets versions add telegram-config --data-file=config/.env
    echo -e "${GREEN}✓ Telegram config stored${NC}"
fi

# Grant secret access
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding kotak-neo-env \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" > /dev/null 2>&1

gcloud secrets add-iam-policy-binding telegram-config \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" > /dev/null 2>&1

# Create startup script
echo -e "\n${YELLOW}Creating VM startup script...${NC}"
cat > startup-script.sh << 'STARTUP_EOF'
#!/bin/bash

# Update system
apt-get update
apt-get install -y python3.12 python3-pip git cron

# Clone repository
cd /opt
if [ ! -d "modular_trade_agent" ]; then
    git clone https://github.com/your-username/modular_trade_agent.git
fi
cd modular_trade_agent

# Install requirements
pip3 install -r requirements.txt --break-system-packages

# Get secrets
gcloud secrets versions access latest --secret="kotak-neo-env" > modules/kotak_neo_auto_trader/kotak_neo.env
gcloud secrets versions access latest --secret="telegram-config" > config/.env

# Create directories
mkdir -p data analysis_results logs

# Setup cron jobs
cat > /etc/cron.d/trading-system << 'EOF'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Analysis and buy orders (Mon-Fri 4:00 PM IST = 10:30 AM UTC)
30 10 * * 1-5 root cd /opt/modular_trade_agent && /usr/bin/python3 -m src.presentation.cli.application analyze --backtest >> /var/log/trading-analysis.log 2>&1
35 10 * * 1-5 root cd /opt/modular_trade_agent && /usr/bin/python3 -m modules.kotak_neo_auto_trader.run_auto_trade --env modules/kotak_neo_auto_trader/kotak_neo.env >> /var/log/trading-buy.log 2>&1

# Sell engine (Mon-Fri 9:15 AM IST = 3:45 AM UTC)
45 3 * * 1-5 root cd /opt/modular_trade_agent && /usr/bin/python3 -m modules.kotak_neo_auto_trader.run_sell_orders >> /var/log/trading-sell.log 2>&1

EOF

chmod 644 /etc/cron.d/trading-system

# Create log rotation
cat > /etc/logrotate.d/trading << 'EOF'
/var/log/trading-*.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
}
EOF

echo "Startup complete" > /tmp/startup-complete
STARTUP_EOF

# Deploy VM
echo -e "\n${YELLOW}Deploying FREE e2-micro VM...${NC}"
gcloud compute instances create trading-system \
    --zone=$ZONE \
    --machine-type=e2-micro \
    --boot-disk-size=30GB \
    --boot-disk-type=pd-standard \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --scopes=cloud-platform \
    --tags=trading-system \
    --metadata-from-file=startup-script=startup-script.sh

# Clean up
rm startup-script.sh

# Wait for VM to be ready
echo -e "\n${YELLOW}Waiting for VM to initialize...${NC}"
sleep 30

# Get VM IP
VM_IP=$(gcloud compute instances describe trading-system --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

# Summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete! 🎉${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Monthly Cost: \$0 (FREE TIER)${NC}"
echo -e "\n${YELLOW}VM Details:${NC}"
echo -e "  Name: trading-system"
echo -e "  Zone: $ZONE"
echo -e "  IP: $VM_IP"
echo -e "  Type: e2-micro (FREE)"
echo -e "\n${YELLOW}Schedule:${NC}"
echo -e "  Analysis & Buy: Mon-Fri @ 4:00 PM IST"
echo -e "  Sell Engine: Mon-Fri @ 9:15 AM - 3:30 PM IST"
echo -e "\n${YELLOW}Next steps:${NC}"
echo -e "  1. SSH to VM: gcloud compute ssh trading-system --zone=$ZONE"
echo -e "  2. View logs: tail -f /var/log/trading-*.log"
echo -e "  3. Update repo URL in startup script (line 8)"
echo -e "  4. Monitor costs: https://console.cloud.google.com/billing"
echo -e "\n${GREEN}Your trading system is now running 24/7 for FREE! 🚀${NC}"
echo -e "${GREEN}========================================${NC}"
