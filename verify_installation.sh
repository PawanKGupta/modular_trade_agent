#!/bin/bash
################################################################################
# Installation Verification Script
# Checks all components of the Modular Trade Agent installation
################################################################################

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Counters
PASS=0
FAIL=0
WARN=0

# Header
echo ""
echo -e "${BLUE}========================================================================${NC}"
echo -e "${CYAN}Modular Trade Agent - Installation Verification${NC}"
echo -e "${BLUE}========================================================================${NC}"
echo ""

# Function to check and report
check_item() {
    local description=$1
    local command=$2
    local type=${3:-required}  # required, optional, info
    
    echo -ne "${CYAN}Checking:${NC} $description ... "
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASS++))
        return 0
    else
        if [ "$type" == "required" ]; then
            echo -e "${RED}✗ FAIL${NC}"
            ((FAIL++))
        elif [ "$type" == "optional" ]; then
            echo -e "${YELLOW}⚠ WARN (optional)${NC}"
            ((WARN++))
        fi
        return 1
    fi
}

check_item_value() {
    local description=$1
    local command=$2
    local type=${3:-info}
    
    echo -ne "${CYAN}Checking:${NC} $description ... "
    result=$(eval "$command" 2>&1)
    echo -e "${GREEN}$result${NC}"
}

# Section 1: System Requirements
echo -e "${BLUE}[1/8] System Requirements${NC}"
echo "----------------------------------------"

check_item "Operating System" "[ -f /etc/os-release ]"
check_item_value "OS Version" "cat /etc/os-release | grep PRETTY_NAME | cut -d'=' -f2 | tr -d '\"'"

check_item "Python 3.8+" "python3 --version | grep -E 'Python 3\.(8|9|1[0-9])'"
check_item_value "Python Version" "python3 --version"

check_item "pip installed" "python3 -m pip --version"
check_item "git installed" "which git"

echo ""

# Section 2: Installation Directory
echo -e "${BLUE}[2/8] Installation Directory${NC}"
echo "----------------------------------------"

INSTALL_DIR="$HOME/modular_trade_agent"

check_item "Installation directory exists" "[ -d $INSTALL_DIR ]"
check_item "Main script exists" "[ -f $INSTALL_DIR/trade_agent.py ]"
check_item "Config directory exists" "[ -d $INSTALL_DIR/config ]"
check_item "Core modules exist" "[ -d $INSTALL_DIR/core ]"
check_item "Backtest modules exist" "[ -d $INSTALL_DIR/backtest ]"

echo ""

# Section 3: Virtual Environment
echo -e "${BLUE}[3/8] Virtual Environment${NC}"
echo "----------------------------------------"

VENV_DIR="$INSTALL_DIR/.venv"

check_item "Virtual environment exists" "[ -d $VENV_DIR ]"
check_item "Python in venv" "[ -f $VENV_DIR/bin/python ]"
check_item "pip in venv" "[ -f $VENV_DIR/bin/pip ]"
check_item "Activate script exists" "[ -f $VENV_DIR/bin/activate ]"

echo ""

# Section 4: Python Dependencies
echo -e "${BLUE}[4/8] Python Dependencies${NC}"
echo "----------------------------------------"

if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
    
    check_item "yfinance installed" "python -c 'import yfinance'"
    check_item "pandas installed" "python -c 'import pandas'"
    check_item "numpy installed" "python -c 'import numpy'"
    check_item "selenium installed" "python -c 'import selenium'"
    check_item "requests installed" "python -c 'import requests'"
    check_item "python-dotenv installed" "python -c 'import dotenv'"
    
    deactivate 2>/dev/null
else
    echo -e "${RED}Virtual environment not found - skipping dependency check${NC}"
    ((FAIL+=6))
fi

echo ""

# Section 5: Configuration
echo -e "${BLUE}[5/8] Configuration${NC}"
echo "----------------------------------------"

CONFIG_FILE="$INSTALL_DIR/cred.env"

check_item "Configuration file exists" "[ -f $CONFIG_FILE ]"

if [ -f "$CONFIG_FILE" ]; then
    check_item "Telegram bot token configured" "grep -q 'TELEGRAM_BOT_TOKEN=' $CONFIG_FILE && ! grep -q 'TELEGRAM_BOT_TOKEN=$' $CONFIG_FILE && ! grep -q 'your_bot_token' $CONFIG_FILE"
    check_item "Telegram chat ID configured" "grep -q 'TELEGRAM_CHAT_ID=' $CONFIG_FILE && ! grep -q 'TELEGRAM_CHAT_ID=$' $CONFIG_FILE && ! grep -q 'your_chat_id' $CONFIG_FILE"
    check_item "Config file permissions (600)" "[ \$(stat -c %a $CONFIG_FILE) = '600' ]" "optional"
fi

echo ""

# Section 6: Launcher Scripts
echo -e "${BLUE}[6/8] Launcher Scripts${NC}"
echo "----------------------------------------"

check_item "run_agent.sh exists" "[ -f $INSTALL_DIR/run_agent.sh ]"
check_item "run_agent.sh executable" "[ -x $INSTALL_DIR/run_agent.sh ]"
check_item "run_agent_backtest.sh exists" "[ -f $INSTALL_DIR/run_agent_backtest.sh ]"
check_item "run_agent_backtest.sh executable" "[ -x $INSTALL_DIR/run_agent_backtest.sh ]"

echo ""

# Section 7: Systemd Service
echo -e "${BLUE}[7/8] Systemd Service (Optional)${NC}"
echo "----------------------------------------"

SERVICE_FILE="/etc/systemd/system/modular-trade-agent.service"
TIMER_FILE="/etc/systemd/system/modular-trade-agent.timer"

if [ -f "$SERVICE_FILE" ]; then
    check_item "Service file exists" "[ -f $SERVICE_FILE ]"
    check_item "Timer file exists" "[ -f $TIMER_FILE ]"
    check_item "Service enabled" "systemctl is-enabled modular-trade-agent.timer" "optional"
    check_item "Timer active" "systemctl is-active modular-trade-agent.timer" "optional"
    
    # Show next scheduled run
    if systemctl is-active --quiet modular-trade-agent.timer; then
        echo -e "${CYAN}Next scheduled run:${NC}"
        systemctl list-timers modular-trade-agent.timer --no-pager | tail -n +2 | head -n 1
    fi
else
    echo -e "${YELLOW}⚠ Systemd service not installed (optional)${NC}"
    echo -e "${CYAN}  To install: Follow prompts in ./setup_ubuntu.sh${NC}"
fi

echo ""

# Section 8: Directory Structure
echo -e "${BLUE}[8/8] Working Directories${NC}"
echo "----------------------------------------"

check_item "Logs directory" "[ -d $INSTALL_DIR/logs ]"
check_item "Data directory" "[ -d $INSTALL_DIR/data ]" "optional"
check_item "Analysis results directory" "[ -d $INSTALL_DIR/analysis_results ]" "optional"
check_item "Backtest reports directory" "[ -d $INSTALL_DIR/backtest_reports ]" "optional"

# Check write permissions
check_item "Logs directory writable" "[ -w $INSTALL_DIR/logs ]"

echo ""

# Section: Additional Checks
echo -e "${BLUE}Additional Information${NC}"
echo "----------------------------------------"

# Disk space
echo -ne "${CYAN}Disk space available:${NC} "
df -h "$INSTALL_DIR" | awk 'NR==2 {print $4}'

# Installation size
echo -ne "${CYAN}Installation size:${NC} "
du -sh "$INSTALL_DIR" 2>/dev/null | cut -f1

# Log files
if [ -d "$INSTALL_DIR/logs" ]; then
    log_count=$(ls -1 "$INSTALL_DIR/logs"/*.log 2>/dev/null | wc -l)
    echo -e "${CYAN}Log files found:${NC} $log_count"
fi

echo ""

# Summary
echo -e "${BLUE}========================================================================${NC}"
echo -e "${CYAN}Verification Summary${NC}"
echo -e "${BLUE}========================================================================${NC}"
echo ""
echo -e "${GREEN}✓ Passed:${NC} $PASS"
echo -e "${RED}✗ Failed:${NC} $FAIL"
echo -e "${YELLOW}⚠ Warnings:${NC} $WARN"
echo ""

# Overall result
if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}========================================================================${NC}"
    echo -e "${GREEN}✅ INSTALLATION VERIFIED SUCCESSFULLY!${NC}"
    echo -e "${GREEN}========================================================================${NC}"
    echo ""
    echo -e "${CYAN}Next Steps:${NC}"
    echo "  1. Test Telegram: cd $INSTALL_DIR && source .venv/bin/activate && python3 test_telegram.py"
    echo "  2. Run agent: cd $INSTALL_DIR && ./run_agent_backtest.sh"
    echo "  3. Check logs: tail -f $INSTALL_DIR/logs/trade_agent_\$(date +%Y%m%d).log"
    echo ""
    
    if [ -f "$SERVICE_FILE" ]; then
        echo -e "${CYAN}Service Management:${NC}"
        echo "  View status:  systemctl status modular-trade-agent.timer"
        echo "  View logs:    journalctl -u modular-trade-agent.service -f"
        echo "  Manual run:   sudo systemctl start modular-trade-agent.service"
        echo ""
    fi
    
    exit 0
else
    echo -e "${RED}========================================================================${NC}"
    echo -e "${RED}⚠ INSTALLATION HAS ISSUES${NC}"
    echo -e "${RED}========================================================================${NC}"
    echo ""
    echo -e "${YELLOW}Recommended Actions:${NC}"
    
    if [ ! -d "$INSTALL_DIR" ]; then
        echo "  • Installation directory not found - run ./setup_ubuntu.sh"
    fi
    
    if [ ! -d "$VENV_DIR" ]; then
        echo "  • Virtual environment missing - run ./setup_ubuntu.sh"
    fi
    
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "  • Configuration missing - create cred.env with Telegram credentials"
    fi
    
    echo ""
    echo -e "${CYAN}Troubleshooting:${NC}"
    echo "  • Re-run installer: ./setup_ubuntu.sh"
    echo "  • Check guide: cat INSTALL_UBUNTU.md"
    echo "  • View errors: cat TROUBLESHOOTING_UBUNTU.md"
    echo ""
    
    exit 1
fi
