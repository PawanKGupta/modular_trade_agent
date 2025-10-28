#!/bin/bash
################################################################################
# Health Check Script for Linux
# Monitors system health and validates configuration
################################################################################

echo "========================================================================"
echo "Modular Trade Agent - Health Check"
echo "========================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

# Check executable
echo "[1/8] Checking executable..."
if [ -f "ModularTradeAgent" ] && [ -x "ModularTradeAgent" ]; then
    SIZE=$(du -sh ModularTradeAgent | cut -f1)
    echo -e "${GREEN}✓ Executable found (${SIZE})${NC}"
else
    echo -e "${RED}✗ Executable not found or not executable${NC}"
    ((ERRORS++))
fi

# Check configuration
echo ""
echo "[2/8] Checking configuration..."
if [ -f "kotak_neo.env" ]; then
    echo -e "${GREEN}✓ Configuration file exists${NC}"
    
    # Check required fields
    REQUIRED_FIELDS=("KOTAK_NEO_CONSUMER_KEY" "KOTAK_NEO_CONSUMER_SECRET" "KOTAK_NEO_MOBILE_NUMBER" "KOTAK_NEO_PASSWORD")
    for FIELD in "${REQUIRED_FIELDS[@]}"; do
        if grep -q "^${FIELD}=" kotak_neo.env; then
            VALUE=$(grep "^${FIELD}=" kotak_neo.env | cut -d'=' -f2)
            if [ -z "$VALUE" ] || [ "$VALUE" = "your_*" ]; then
                echo -e "${YELLOW}⚠ ${FIELD} not configured${NC}"
                ((WARNINGS++))
            fi
        else
            echo -e "${RED}✗ ${FIELD} missing${NC}"
            ((ERRORS++))
        fi
    done
else
    echo -e "${RED}✗ Configuration file not found${NC}"
    ((ERRORS++))
fi

# Check data directory
echo ""
echo "[3/8] Checking data directory..."
if [ -d "data" ]; then
    DATA_COUNT=$(find data -name "*.json" 2>/dev/null | wc -l)
    echo -e "${GREEN}✓ Data directory exists (${DATA_COUNT} JSON files)${NC}"
else
    echo -e "${YELLOW}⚠ Data directory not found (will be created on first run)${NC}"
    ((WARNINGS++))
fi

# Check disk space
echo ""
echo "[4/8] Checking disk space..."
AVAILABLE=$(df -h . | tail -1 | awk '{print $4}')
USAGE=$(df -h . | tail -1 | awk '{print $5}' | sed 's/%//')
echo "  Available: $AVAILABLE (${USAGE}% used)"
if [ "$USAGE" -gt 90 ]; then
    echo -e "${RED}✗ Low disk space!${NC}"
    ((ERRORS++))
elif [ "$USAGE" -gt 80 ]; then
    echo -e "${YELLOW}⚠ Disk space getting low${NC}"
    ((WARNINGS++))
else
    echo -e "${GREEN}✓ Sufficient disk space${NC}"
fi

# Check memory
echo ""
echo "[5/8] Checking memory..."
if command -v free &> /dev/null; then
    TOTAL_MEM=$(free -h | awk '/^Mem:/ {print $2}')
    AVAIL_MEM=$(free -h | awk '/^Mem:/ {print $7}')
    echo "  Total: $TOTAL_MEM | Available: $AVAIL_MEM"
    echo -e "${GREEN}✓ Memory check complete${NC}"
else
    echo -e "${YELLOW}⚠ Unable to check memory (free command not available)${NC}"
    ((WARNINGS++))
fi

# Check internet connectivity
echo ""
echo "[6/8] Checking internet connectivity..."
if ping -c 1 -W 2 8.8.8.8 &> /dev/null; then
    echo -e "${GREEN}✓ Internet connectivity available${NC}"
else
    echo -e "${RED}✗ No internet connectivity${NC}"
    ((ERRORS++))
fi

# Check if service is running
echo ""
echo "[7/8] Checking service status..."
if systemctl is-active --quiet tradeagent.service 2>/dev/null; then
    echo -e "${GREEN}✓ Service is running${NC}"
    systemctl status tradeagent.service --no-pager | head -n 5
elif [ -f "/etc/systemd/system/tradeagent.service" ]; then
    echo -e "${YELLOW}⚠ Service installed but not running${NC}"
    ((WARNINGS++))
else
    echo -e "${YELLOW}⚠ Service not installed${NC}"
    echo "  Run ./install_service.sh to install as a service"
    ((WARNINGS++))
fi

# Check logs
echo ""
echo "[8/8] Checking logs..."
if [ -d "logs" ]; then
    LOG_COUNT=$(find logs -name "*.log" 2>/dev/null | wc -l)
    if [ $LOG_COUNT -gt 0 ]; then
        LATEST_LOG=$(find logs -name "*.log" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
        LOG_SIZE=$(du -sh "$LATEST_LOG" | cut -f1)
        LOG_LINES=$(wc -l < "$LATEST_LOG")
        echo -e "${GREEN}✓ Logs found (${LOG_COUNT} files)${NC}"
        echo "  Latest: $LATEST_LOG ($LOG_SIZE, $LOG_LINES lines)"
        
        # Check for recent errors
        if [ -f "$LATEST_LOG" ]; then
            ERROR_COUNT=$(grep -c "ERROR" "$LATEST_LOG" 2>/dev/null || echo "0")
            if [ "$ERROR_COUNT" -gt 0 ]; then
                echo -e "${YELLOW}⚠ Found ${ERROR_COUNT} errors in latest log${NC}"
                echo "  Last 3 errors:"
                grep "ERROR" "$LATEST_LOG" | tail -3 | sed 's/^/    /'
                ((WARNINGS++))
            fi
        fi
    else
        echo -e "${YELLOW}⚠ No log files found${NC}"
        ((WARNINGS++))
    fi
else
    echo -e "${YELLOW}⚠ Logs directory not found${NC}"
    ((WARNINGS++))
fi

# Summary
echo ""
echo "========================================================================"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ HEALTH CHECK PASSED${NC}"
    echo "All systems operational!"
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ HEALTH CHECK COMPLETED WITH WARNINGS${NC}"
    echo "Found $WARNINGS warning(s)"
    echo "System is functional but attention may be needed"
else
    echo -e "${RED}❌ HEALTH CHECK FAILED${NC}"
    echo "Found $ERRORS error(s) and $WARNINGS warning(s)"
    echo "Please address the errors before running"
fi
echo "========================================================================"
echo ""

exit $ERRORS
