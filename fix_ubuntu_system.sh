#!/bin/bash
################################################################################
# Ubuntu System Troubleshooting and Fix Script
# Fixes common system issues before running the main installer
################################################################################

set +e  # Don't exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}========================================================================${NC}"
echo -e "${CYAN}Ubuntu System Troubleshooting & Fix Script${NC}"
echo -e "${CYAN}========================================================================${NC}"
echo ""

# Fix 1: command-not-found package issue
echo -e "${CYAN}[1/5] Fixing command-not-found package...${NC}"
if [ -f /usr/lib/cnf-update-db ]; then
    # Remove the problematic post-invoke hook temporarily
    sudo rm -f /etc/apt/apt.conf.d/50command-not-found 2>/dev/null
    echo -e "${GREEN}✓ Removed problematic apt hook${NC}"
else
    echo -e "${GREEN}✓ No command-not-found issues detected${NC}"
fi

# Fix 2: Repair broken apt-pkg Python bindings
echo ""
echo -e "${CYAN}[2/5] Repairing Python apt bindings...${NC}"
if python3 -c "import apt_pkg" 2>/dev/null; then
    echo -e "${GREEN}✓ Python apt bindings OK${NC}"
else
    echo -e "${YELLOW}⚠ Python apt bindings missing, attempting repair...${NC}"
    sudo apt-get install --reinstall python3-apt -y -qq 2>/dev/null || true
    if python3 -c "import apt_pkg" 2>/dev/null; then
        echo -e "${GREEN}✓ Python apt bindings repaired${NC}"
    else
        echo -e "${YELLOW}⚠ Could not repair, but continuing (non-critical)${NC}"
    fi
fi

# Fix 3: Update package lists
echo ""
echo -e "${CYAN}[3/5] Updating package lists...${NC}"
sudo apt-get update -qq 2>&1 | grep -v "cnf-update-db" | grep -v "command-not-found" || true
echo -e "${GREEN}✓ Package lists updated${NC}"

# Fix 4: Fix broken dependencies
echo ""
echo -e "${CYAN}[4/5] Fixing broken dependencies...${NC}"
sudo apt-get install -f -y -qq 2>&1 | grep -v "cnf-update-db" || true
echo -e "${GREEN}✓ Dependencies checked${NC}"

# Fix 5: Clean apt cache
echo ""
echo -e "${CYAN}[5/5] Cleaning apt cache...${NC}"
sudo apt-get clean
sudo apt-get autoclean -y -qq
echo -e "${GREEN}✓ Cache cleaned${NC}"

# Summary
echo ""
echo -e "${CYAN}========================================================================${NC}"
echo -e "${GREEN}System Troubleshooting Complete!${NC}"
echo -e "${CYAN}========================================================================${NC}"
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo "  1. Run the main installer: ./setup_ubuntu.sh"
echo "  2. Or continue with manual installation steps"
echo ""
echo -e "${YELLOW}Note: The 'cnf-update-db' error is cosmetic and won't affect the installation.${NC}"
echo ""
