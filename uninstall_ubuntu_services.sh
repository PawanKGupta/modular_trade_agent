#!/bin/bash

################################################################################
# Modular Trade Agent - Ubuntu Services Uninstall Script
# 
# This script removes all systemd services for the trading agent:
# - Stops all running services
# - Disables all timers
# - Removes all service files
# - Reloads systemd daemon
#
# Usage: sudo ./uninstall_ubuntu_services.sh
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}    Modular Trade Agent - Services Uninstall${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}✗ Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Running as root${NC}"
echo ""

# List of all service names (without .service/.timer extension)
SERVICES=(
    "tradeagent-analysis"
    "tradeagent-autotrade"
    "tradeagent-monitor"
    "tradeagent-monitor-stop"
    "tradeagent-sell"
    "tradeagent-eod"
    "tradeagent-unified"
)

################################################################################
# Step 1: Stop all running services
################################################################################

echo -e "${BLUE}[1/4] Stopping all services...${NC}"

for service in "${SERVICES[@]}"; do
    # Stop service if it exists
    if systemctl list-units --full -all | grep -q "${service}.service"; then
        if systemctl is-active --quiet "${service}.service"; then
            echo -e "${YELLOW}  Stopping ${service}.service...${NC}"
            systemctl stop "${service}.service" 2>/dev/null || true
        fi
    fi
    
    # Stop timer if it exists
    if systemctl list-units --full -all | grep -q "${service}.timer"; then
        if systemctl is-active --quiet "${service}.timer"; then
            echo -e "${YELLOW}  Stopping ${service}.timer...${NC}"
            systemctl stop "${service}.timer" 2>/dev/null || true
        fi
    fi
done

echo -e "${GREEN}✓ All services stopped${NC}"
echo ""

################################################################################
# Step 2: Disable all services
################################################################################

echo -e "${BLUE}[2/4] Disabling all services...${NC}"

for service in "${SERVICES[@]}"; do
    # Disable service if it exists
    if systemctl list-unit-files | grep -q "${service}.service"; then
        if systemctl is-enabled --quiet "${service}.service" 2>/dev/null; then
            echo -e "${YELLOW}  Disabling ${service}.service...${NC}"
            systemctl disable "${service}.service" 2>/dev/null || true
        fi
    fi
    
    # Disable timer if it exists
    if systemctl list-unit-files | grep -q "${service}.timer"; then
        if systemctl is-enabled --quiet "${service}.timer" 2>/dev/null; then
            echo -e "${YELLOW}  Disabling ${service}.timer...${NC}"
            systemctl disable "${service}.timer" 2>/dev/null || true
        fi
    fi
done

echo -e "${GREEN}✓ All services disabled${NC}"
echo ""

################################################################################
# Step 3: Remove service files
################################################################################

echo -e "${BLUE}[3/4] Removing service files...${NC}"

for service in "${SERVICES[@]}"; do
    # Remove service file
    if [ -f "/etc/systemd/system/${service}.service" ]; then
        echo -e "${YELLOW}  Removing ${service}.service...${NC}"
        rm -f "/etc/systemd/system/${service}.service"
    fi
    
    # Remove timer file
    if [ -f "/etc/systemd/system/${service}.timer" ]; then
        echo -e "${YELLOW}  Removing ${service}.timer...${NC}"
        rm -f "/etc/systemd/system/${service}.timer"
    fi
done

echo -e "${GREEN}✓ All service files removed${NC}"
echo ""

################################################################################
# Step 4: Reload systemd daemon
################################################################################

echo -e "${BLUE}[4/4] Reloading systemd daemon...${NC}"

systemctl daemon-reload
systemctl reset-failed

echo -e "${GREEN}✓ Systemd daemon reloaded${NC}"
echo ""

################################################################################
# Verification
################################################################################

echo -e "${BLUE}Verifying removal...${NC}"
echo ""

REMAINING=$(systemctl list-units --full -all | grep -c "tradeagent" || true)

if [ "$REMAINING" -eq 0 ]; then
    echo -e "${GREEN}✓ All services successfully removed${NC}"
else
    echo -e "${YELLOW}⚠ Warning: ${REMAINING} services still found${NC}"
    echo -e "${YELLOW}Run: systemctl list-units --all | grep tradeagent${NC}"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Uninstall Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${BLUE}📋 What was removed:${NC}"
echo -e "  - All tradeagent systemd services"
echo -e "  - All tradeagent systemd timers"
echo -e "  - Service files from /etc/systemd/system/"
echo ""

echo -e "${BLUE}📁 What was NOT removed:${NC}"
echo -e "  - Project files in ~/modular_trade_agent"
echo -e "  - Python virtual environment (.venv)"
echo -e "  - Configuration files (cred.env, kotak_neo.env)"
echo -e "  - Logs and data files"
echo ""

echo -e "${YELLOW}Note: To completely remove the project, delete the directory manually:${NC}"
echo -e "${YELLOW}  rm -rf ~/modular_trade_agent${NC}"
echo ""
