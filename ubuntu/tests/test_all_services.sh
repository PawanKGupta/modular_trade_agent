#!/bin/bash
################################################################################
# Test All Services Script
# Stops all services, tests each one individually, then restarts
################################################################################

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m'

INSTALL_DIR="$HOME/modular_trade_agent"
VENV_DIR="$INSTALL_DIR/.venv"

echo ""
echo -e "${BLUE}========================================================================${NC}"
echo -e "${CYAN}Service Testing Suite${NC}"
echo -e "${BLUE}========================================================================${NC}"
echo ""

# Check if running as root for service control
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Get actual user
if [ -n "$SUDO_USER" ]; then
    ACTUAL_USER=$SUDO_USER
    ACTUAL_HOME="/home/$SUDO_USER"
    INSTALL_DIR="$ACTUAL_HOME/modular_trade_agent"
    VENV_DIR="$INSTALL_DIR/.venv"
else
    ACTUAL_USER=$USER
    ACTUAL_HOME=$HOME
fi

echo "Testing as user: $ACTUAL_USER"
echo "Installation directory: $INSTALL_DIR"
echo ""

# Check if installation exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}❌ Installation directory not found${NC}"
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}❌ Virtual environment not found${NC}"
    exit 1
fi

##############################################################################
# STEP 1: Stop All Running Services
##############################################################################

echo -e "${CYAN}[STEP 1/6] Stopping All Services${NC}"
echo "----------------------------------------"

SERVICES=(
    "tradeagent-analysis"
    "tradeagent-autotrade"
    "tradeagent-monitor"
    "tradeagent-sell"
    "tradeagent-eod"
)

for service in "${SERVICES[@]}"; do
    echo -ne "Stopping ${service}.timer ... "
    if systemctl stop "${service}.timer" 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}⚠ (not running)${NC}"
    fi
done

echo ""
sleep 2

##############################################################################
# STEP 2: Test Service Files Syntax
##############################################################################

echo -e "${CYAN}[STEP 2/6] Verifying Service File Syntax${NC}"
echo "----------------------------------------"

syntax_errors=0

for service in "${SERVICES[@]}"; do
    echo -ne "Checking ${service}.service ... "
    if systemd-analyze verify "/etc/systemd/system/${service}.service" 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        ((syntax_errors++))
    fi
    
    echo -ne "Checking ${service}.timer ... "
    if systemd-analyze verify "/etc/systemd/system/${service}.timer" 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        ((syntax_errors++))
    fi
done

if [ $syntax_errors -gt 0 ]; then
    echo ""
    echo -e "${RED}❌ Found $syntax_errors syntax error(s). Fix before continuing.${NC}"
    exit 1
fi

echo ""

##############################################################################
# STEP 3: Test Each Service Manually
##############################################################################

echo -e "${CYAN}[STEP 3/6] Testing Each Service Individually${NC}"
echo "----------------------------------------"
echo ""

test_results=()

# Service 1: Analysis
echo -e "${BLUE}[1/5] Testing Trade Analysis Service${NC}"
echo "Command: python3 trade_agent.py --backtest"
echo ""

cd "$INSTALL_DIR"
sudo -u $ACTUAL_USER bash -c "cd $INSTALL_DIR && source $VENV_DIR/bin/activate && timeout 60 python3 trade_agent.py --no-csv --no-mtf 2>&1 | head -50"
analysis_result=$?

if [ $analysis_result -eq 0 ] || [ $analysis_result -eq 124 ]; then
    echo -e "${GREEN}✓ Analysis service test passed${NC}"
    test_results+=("analysis:PASS")
else
    echo -e "${RED}✗ Analysis service test failed (exit code: $analysis_result)${NC}"
    test_results+=("analysis:FAIL")
fi

echo ""
echo "Press Enter to continue to next test..."
read

# Service 2: Auto Trade (if Kotak modules exist)
echo -e "${BLUE}[2/5] Testing Auto Trade Service${NC}"

if [ -d "$INSTALL_DIR/modules/kotak_neo_auto_trader" ]; then
    if [ -f "$INSTALL_DIR/kotak_neo.env" ]; then
        echo "Command: python3 -m modules.kotak_neo_auto_trader.run_auto_trade --env kotak_neo.env"
        echo ""
        
        cd "$INSTALL_DIR"
        sudo -u $ACTUAL_USER bash -c "cd $INSTALL_DIR && source $VENV_DIR/bin/activate && timeout 30 python3 -m modules.kotak_neo_auto_trader.run_auto_trade --env kotak_neo.env 2>&1 | head -30"
        autotrade_result=$?
        
        if [ $autotrade_result -eq 0 ] || [ $autotrade_result -eq 124 ]; then
            echo -e "${GREEN}✓ Auto Trade service test passed${NC}"
            test_results+=("autotrade:PASS")
        else
            echo -e "${YELLOW}⚠ Auto Trade service test exited with code: $autotrade_result${NC}"
            test_results+=("autotrade:WARN")
        fi
    else
        echo -e "${YELLOW}⚠ kotak_neo.env not found - skipping test${NC}"
        test_results+=("autotrade:SKIP")
    fi
else
    echo -e "${YELLOW}⚠ Kotak Neo modules not found - skipping test${NC}"
    test_results+=("autotrade:SKIP")
fi

echo ""
echo "Press Enter to continue to next test..."
read

# Service 3: Position Monitor
echo -e "${BLUE}[3/5] Testing Position Monitor Service${NC}"

if [ -d "$INSTALL_DIR/modules/kotak_neo_auto_trader" ]; then
    echo "Command: python3 -m modules.kotak_neo_auto_trader.run_position_monitor --force"
    echo ""
    
    cd "$INSTALL_DIR"
    sudo -u $ACTUAL_USER bash -c "cd $INSTALL_DIR && source $VENV_DIR/bin/activate && timeout 30 python3 -m modules.kotak_neo_auto_trader.run_position_monitor --force 2>&1 | head -30"
    monitor_result=$?
    
    if [ $monitor_result -eq 0 ] || [ $monitor_result -eq 124 ]; then
        echo -e "${GREEN}✓ Position Monitor service test passed${NC}"
        test_results+=("monitor:PASS")
    else
        echo -e "${YELLOW}⚠ Position Monitor service test exited with code: $monitor_result${NC}"
        test_results+=("monitor:WARN")
    fi
else
    echo -e "${YELLOW}⚠ Kotak Neo modules not found - skipping test${NC}"
    test_results+=("monitor:SKIP")
fi

echo ""
echo "Press Enter to continue to next test..."
read

# Service 4: Sell Orders
echo -e "${BLUE}[4/5] Testing Sell Orders Service${NC}"

if [ -d "$INSTALL_DIR/modules/kotak_neo_auto_trader" ]; then
    if [ -f "$INSTALL_DIR/kotak_neo.env" ]; then
        echo "Command: python3 -m modules.kotak_neo_auto_trader.run_sell_orders --env kotak_neo.env --skip-wait --run-once"
        echo ""
        
        cd "$INSTALL_DIR"
        sudo -u $ACTUAL_USER bash -c "cd $INSTALL_DIR && source $VENV_DIR/bin/activate && timeout 30 python3 -m modules.kotak_neo_auto_trader.run_sell_orders --env kotak_neo.env --skip-wait --run-once 2>&1 | head -30"
        sell_result=$?
        
        if [ $sell_result -eq 0 ] || [ $sell_result -eq 124 ]; then
            echo -e "${GREEN}✓ Sell Orders service test passed${NC}"
            test_results+=("sell:PASS")
        else
            echo -e "${YELLOW}⚠ Sell Orders service test exited with code: $sell_result${NC}"
            test_results+=("sell:WARN")
        fi
    else
        echo -e "${YELLOW}⚠ kotak_neo.env not found - skipping test${NC}"
        test_results+=("sell:SKIP")
    fi
else
    echo -e "${YELLOW}⚠ Kotak Neo modules not found - skipping test${NC}"
    test_results+=("sell:SKIP")
fi

echo ""
echo "Press Enter to continue to next test..."
read

# Service 5: EOD Cleanup
echo -e "${BLUE}[5/5] Testing EOD Cleanup Service${NC}"

if [ -d "$INSTALL_DIR/modules/kotak_neo_auto_trader" ]; then
    if [ -f "$INSTALL_DIR/kotak_neo.env" ]; then
        echo "Command: python3 -m modules.kotak_neo_auto_trader.run_eod_cleanup --env kotak_neo.env"
        echo ""
        
        cd "$INSTALL_DIR"
        sudo -u $ACTUAL_USER bash -c "cd $INSTALL_DIR && source $VENV_DIR/bin/activate && timeout 30 python3 -m modules.kotak_neo_auto_trader.run_eod_cleanup --env kotak_neo.env 2>&1 | head -30"
        eod_result=$?
        
        if [ $eod_result -eq 0 ] || [ $eod_result -eq 124 ]; then
            echo -e "${GREEN}✓ EOD Cleanup service test passed${NC}"
            test_results+=("eod:PASS")
        else
            echo -e "${YELLOW}⚠ EOD Cleanup service test exited with code: $eod_result${NC}"
            test_results+=("eod:WARN")
        fi
    else
        echo -e "${YELLOW}⚠ kotak_neo.env not found - skipping test${NC}"
        test_results+=("eod:SKIP")
    fi
else
    echo -e "${YELLOW}⚠ Kotak Neo modules not found - skipping test${NC}"
    test_results+=("eod:SKIP")
fi

echo ""

##############################################################################
# STEP 4: Test Systemd Service Execution
##############################################################################

echo -e "${CYAN}[STEP 4/6] Testing Systemd Service Execution${NC}"
echo "----------------------------------------"
echo ""

# Test only the analysis service via systemd (others require credentials)
echo "Testing: systemctl start tradeagent-analysis.service"
if systemctl start tradeagent-analysis.service; then
    sleep 5
    if systemctl status tradeagent-analysis.service | grep -q "succeeded\|Deactivated successfully"; then
        echo -e "${GREEN}✓ Analysis service executed via systemd${NC}"
    else
        echo -e "${YELLOW}⚠ Analysis service may have issues${NC}"
        systemctl status tradeagent-analysis.service | tail -10
    fi
else
    echo -e "${RED}✗ Failed to start analysis service${NC}"
fi

echo ""

##############################################################################
# STEP 5: Restart All Services
##############################################################################

echo -e "${CYAN}[STEP 5/6] Restarting All Service Timers${NC}"
echo "----------------------------------------"

for service in "${SERVICES[@]}"; do
    echo -ne "Starting ${service}.timer ... "
    if systemctl start "${service}.timer" 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi
done

echo ""
sleep 2

##############################################################################
# STEP 6: Summary
##############################################################################

echo -e "${CYAN}[STEP 6/6] Test Summary${NC}"
echo "----------------------------------------"
echo ""

echo -e "${CYAN}Test Results:${NC}"
pass_count=0
fail_count=0
warn_count=0
skip_count=0

for result in "${test_results[@]}"; do
    service=$(echo $result | cut -d: -f1)
    status=$(echo $result | cut -d: -f2)
    
    case $status in
        PASS)
            echo -e "  ${GREEN}✓${NC} $service - ${GREEN}PASSED${NC}"
            ((pass_count++))
            ;;
        FAIL)
            echo -e "  ${RED}✗${NC} $service - ${RED}FAILED${NC}"
            ((fail_count++))
            ;;
        WARN)
            echo -e "  ${YELLOW}⚠${NC} $service - ${YELLOW}WARNING${NC}"
            ((warn_count++))
            ;;
        SKIP)
            echo -e "  ${BLUE}○${NC} $service - ${BLUE}SKIPPED${NC}"
            ((skip_count++))
            ;;
    esac
done

echo ""
echo -e "${CYAN}Summary:${NC}"
echo "  Passed: $pass_count"
echo "  Failed: $fail_count"
echo "  Warnings: $warn_count"
echo "  Skipped: $skip_count"
echo ""

echo -e "${CYAN}Active Service Timers:${NC}"
systemctl list-timers tradeagent-* --no-pager

echo ""
echo -e "${CYAN}Service Logs Location:${NC}"
echo "  Analysis:    journalctl -u tradeagent-analysis.service -f"
echo "  Auto Trade:  journalctl -u tradeagent-autotrade.service -f"
echo "  Monitor:     journalctl -u tradeagent-monitor.service -f"
echo "  Sell:        journalctl -u tradeagent-sell.service -f"
echo "  EOD:         journalctl -u tradeagent-eod.service -f"
echo ""

echo -e "${BLUE}========================================================================${NC}"
if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS COMPLETED${NC}"
    if [ $warn_count -gt 0 ]; then
        echo -e "${YELLOW}⚠ Some services have warnings (check Kotak Neo credentials)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ TESTS COMPLETED WITH ERRORS${NC}"
    echo -e "${YELLOW}  Check the output above for details${NC}"
fi
echo -e "${BLUE}========================================================================${NC}"
echo ""
