#!/bin/bash
################################################################################
# Cleanup Old Services
# Removes any duplicate or old service configurations
################################################################################

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}========================================================================${NC}"
echo -e "${CYAN}Cleanup Old Services${NC}"
echo -e "${CYAN}========================================================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ This script must be run as root (use sudo)${NC}"
    exit 1
fi

echo "This will remove any old/duplicate service configurations."
echo ""
read -p "Continue? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled"
    exit 0
fi

echo ""
echo -e "${CYAN}Checking for old services...${NC}"
echo ""

# List of possible old services to check
OLD_SERVICES=(
    "modular-trade-agent"
    "tradeagent-morning"
)

# List of current services (should keep)
CURRENT_SERVICES=(
    "tradeagent-analysis"
    "tradeagent-autotrade"
    "tradeagent-monitor"
    "tradeagent-sell"
    "tradeagent-eod"
)

removed_count=0

# Check and remove old services
for service in "${OLD_SERVICES[@]}"; do
    if [ -f "/etc/systemd/system/${service}.service" ] || [ -f "/etc/systemd/system/${service}.timer" ]; then
        echo -e "${YELLOW}Found old service: $service${NC}"
        
        # Stop and disable
        systemctl stop "${service}.timer" 2>/dev/null
        systemctl stop "${service}.service" 2>/dev/null
        systemctl disable "${service}.timer" 2>/dev/null
        systemctl disable "${service}.service" 2>/dev/null
        
        # Remove files
        rm -f "/etc/systemd/system/${service}.service"
        rm -f "/etc/systemd/system/${service}.timer"
        
        echo -e "${GREEN}  ✓ Removed${NC}"
        ((removed_count++))
    fi
done

if [ $removed_count -eq 0 ]; then
    echo -e "${GREEN}✓ No old services found${NC}"
else
    echo ""
    echo -e "${GREEN}✓ Removed $removed_count old service(s)${NC}"
    
    # Reload systemd
    echo ""
    echo -e "${CYAN}Reloading systemd...${NC}"
    systemctl daemon-reload
fi

echo ""
echo -e "${CYAN}Current active services:${NC}"
echo ""

# List current services
for service in "${CURRENT_SERVICES[@]}"; do
    if systemctl is-enabled "${service}.timer" &>/dev/null; then
        status=$(systemctl is-active "${service}.timer")
        if [ "$status" = "active" ]; then
            echo -e "  ${GREEN}✓${NC} ${service}.timer - ${GREEN}active${NC}"
        else
            echo -e "  ${YELLOW}⚠${NC} ${service}.timer - ${YELLOW}inactive${NC}"
        fi
    else
        echo -e "  ${RED}✗${NC} ${service}.timer - ${RED}not installed${NC}"
    fi
done

echo ""
echo -e "${CYAN}Next scheduled runs:${NC}"
systemctl list-timers tradeagent-* --no-pager 2>/dev/null | head -10

echo ""
echo -e "${GREEN}========================================================================${NC}"
echo -e "${GREEN}✅ Cleanup Complete${NC}"
echo -e "${GREEN}========================================================================${NC}"
echo ""
