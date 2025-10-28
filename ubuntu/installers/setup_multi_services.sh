#!/bin/bash
################################################################################
# Multi-Service Systemd Setup (Optional Advanced Configuration)
# Creates multiple services for different execution modes
################################################################################

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}========================================================================${NC}"
echo -e "${CYAN}Multi-Service Systemd Setup${NC}"
echo -e "${CYAN}========================================================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ This script must be run as root (use sudo)${NC}"
    exit 1
fi

INSTALL_DIR="$HOME/modular_trade_agent"
if [ -n "$SUDO_USER" ]; then
    INSTALL_DIR="/home/$SUDO_USER/modular_trade_agent"
    ACTUAL_USER=$SUDO_USER
else
    ACTUAL_USER=$USER
fi

VENV_DIR="$INSTALL_DIR/.venv"
ACTUAL_GROUP=$(id -gn $ACTUAL_USER)

echo "Installation directory: $INSTALL_DIR"
echo "Running as user: $ACTUAL_USER:$ACTUAL_GROUP"
echo ""

# Check if installation exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}❌ Installation directory not found: $INSTALL_DIR${NC}"
    echo "Run ./setup_ubuntu.sh first"
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}❌ Virtual environment not found${NC}"
    exit 1
fi

echo -e "${CYAN}This will create the following services:${NC}"
echo "  1. Main Analysis Service (4:00 PM daily) - Stock analysis and signals"
echo "  2. Morning Brief Service (9:00 AM daily) - Market open summary"
echo "  3. EOD Summary Service (3:30 PM daily) - End of day recap"
echo ""
echo -e "${YELLOW}Note: This is optional - the basic single-service setup works fine.${NC}"
echo ""

read -p "Continue with multi-service setup? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled"
    exit 0
fi

echo ""
echo -e "${CYAN}[1/3] Creating Main Analysis Service${NC}"
echo "----------------------------------------"

# Main Analysis Service (4:00 PM)
cat > /etc/systemd/system/tradeagent-analysis.service << EOF
[Unit]
Description=Trade Agent - Main Analysis Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$ACTUAL_USER
Group=$ACTUAL_GROUP
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/trade_agent.py --backtest
Restart=on-failure
RestartSec=60
StandardOutput=append:$INSTALL_DIR/logs/analysis_service.log
StandardError=append:$INSTALL_DIR/logs/analysis_service_error.log

Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Analysis Timer (4:00 PM)
cat > /etc/systemd/system/tradeagent-analysis.timer << EOF
[Unit]
Description=Trade Agent Analysis Timer (4:00 PM)
Requires=tradeagent-analysis.service

[Timer]
OnCalendar=Mon-Fri 16:00:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ Main analysis service created${NC}"

echo ""
echo -e "${CYAN}[2/3] Creating Morning Brief Service${NC}"
echo "----------------------------------------"

# Create morning brief script
cat > $INSTALL_DIR/morning_brief.py << 'EOFSCRIPT'
#!/usr/bin/env python3
"""Morning Brief - Quick market summary at market open"""

from core.telegram import send_telegram
from datetime import datetime
import yfinance as yf

def get_morning_brief():
    """Generate morning market brief"""
    
    # Get NIFTY 50 data
    nifty = yf.Ticker("^NSEI")
    hist = nifty.history(period="5d")
    
    if hist.empty:
        return "Unable to fetch market data"
    
    current = hist['Close'].iloc[-1]
    prev = hist['Close'].iloc[-2]
    change = ((current - prev) / prev) * 100
    
    message = f"""
🌅 Morning Market Brief - {datetime.now().strftime('%d %b %Y')}

📊 NIFTY 50: {current:.2f} ({change:+.2f}%)

🔔 Trade Agent will run analysis at 4:00 PM IST
    
Good luck trading! 📈
"""
    
    send_telegram(message)
    print("Morning brief sent")

if __name__ == "__main__":
    get_morning_brief()
EOFSCRIPT

chmod +x $INSTALL_DIR/morning_brief.py

# Morning Brief Service (9:00 AM)
cat > /etc/systemd/system/tradeagent-morning.service << EOF
[Unit]
Description=Trade Agent - Morning Brief Service
After=network-online.target

[Service]
Type=oneshot
User=$ACTUAL_USER
Group=$ACTUAL_GROUP
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/morning_brief.py
StandardOutput=append:$INSTALL_DIR/logs/morning_service.log
StandardError=append:$INSTALL_DIR/logs/morning_service_error.log

Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
EOF

# Morning Timer (9:00 AM)
cat > /etc/systemd/system/tradeagent-morning.timer << EOF
[Unit]
Description=Trade Agent Morning Brief Timer (9:00 AM)
Requires=tradeagent-morning.service

[Timer]
OnCalendar=Mon-Fri 09:00:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ Morning brief service created${NC}"

echo ""
echo -e "${CYAN}[3/3] Creating EOD Summary Service${NC}"
echo "----------------------------------------"

# Create EOD summary script
cat > $INSTALL_DIR/eod_summary.py << 'EOFSCRIPT'
#!/usr/bin/env python3
"""End of Day Summary - Quick recap before market close"""

from core.telegram import send_telegram
from datetime import datetime
import yfinance as yf

def get_eod_summary():
    """Generate end of day summary"""
    
    # Get NIFTY 50 data
    nifty = yf.Ticker("^NSEI")
    hist = nifty.history(period="1d", interval="1m")
    
    if hist.empty:
        return
    
    open_price = hist['Open'].iloc[0]
    current = hist['Close'].iloc[-1]
    high = hist['High'].max()
    low = hist['Low'].min()
    
    change = ((current - open_price) / open_price) * 100
    
    message = f"""
🌆 End of Day Summary - {datetime.now().strftime('%d %b %Y')}

📊 NIFTY 50 Today:
   Open: {open_price:.2f}
   High: {high:.2f}
   Low: {low:.2f}
   Current: {current:.2f} ({change:+.2f}%)

⏰ Analysis will run at 4:00 PM with buy signals for tomorrow

Have a great evening! 🌙
"""
    
    send_telegram(message)
    print("EOD summary sent")

if __name__ == "__main__":
    get_eod_summary()
EOFSCRIPT

chmod +x $INSTALL_DIR/eod_summary.py

# EOD Summary Service (3:30 PM)
cat > /etc/systemd/system/tradeagent-eod.service << EOF
[Unit]
Description=Trade Agent - EOD Summary Service
After=network-online.target

[Service]
Type=oneshot
User=$ACTUAL_USER
Group=$ACTUAL_GROUP
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/eod_summary.py
StandardOutput=append:$INSTALL_DIR/logs/eod_service.log
StandardError=append:$INSTALL_DIR/logs/eod_service_error.log

Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
EOF

# EOD Timer (3:30 PM)
cat > /etc/systemd/system/tradeagent-eod.timer << EOF
[Unit]
Description=Trade Agent EOD Summary Timer (3:30 PM)
Requires=tradeagent-eod.service

[Timer]
OnCalendar=Mon-Fri 15:30:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}✓ EOD summary service created${NC}"

echo ""
echo -e "${CYAN}Reloading systemd...${NC}"
systemctl daemon-reload

echo ""
echo -e "${CYAN}Enabling and starting services...${NC}"

# Enable and start all timers
systemctl enable tradeagent-analysis.timer
systemctl enable tradeagent-morning.timer
systemctl enable tradeagent-eod.timer

systemctl start tradeagent-analysis.timer
systemctl start tradeagent-morning.timer
systemctl start tradeagent-eod.timer

echo ""
echo -e "${GREEN}========================================================================${NC}"
echo -e "${GREEN}✅ MULTI-SERVICE SETUP COMPLETE${NC}"
echo -e "${GREEN}========================================================================${NC}"
echo ""

echo -e "${CYAN}Services Created:${NC}"
echo "  1. Main Analysis  - Daily at 4:00 PM IST"
echo "  2. Morning Brief  - Daily at 9:00 AM IST"
echo "  3. EOD Summary    - Daily at 3:30 PM IST"
echo ""

echo -e "${CYAN}Service Management:${NC}"
echo "  View all timers:  systemctl list-timers tradeagent-*"
echo "  Analysis logs:    journalctl -u tradeagent-analysis.service -f"
echo "  Morning logs:     journalctl -u tradeagent-morning.service -f"
echo "  EOD logs:         journalctl -u tradeagent-eod.service -f"
echo ""

echo -e "${CYAN}Manual Execution:${NC}"
echo "  Analysis:  sudo systemctl start tradeagent-analysis.service"
echo "  Morning:   sudo systemctl start tradeagent-morning.service"
echo "  EOD:       sudo systemctl start tradeagent-eod.service"
echo ""

echo -e "${CYAN}Stop All Services:${NC}"
echo "  sudo systemctl stop tradeagent-*.timer"
echo ""

echo -e "${CYAN}Next Scheduled Runs:${NC}"
systemctl list-timers tradeagent-* --no-pager

echo ""
