#!/bin/bash
# Bash script to run E2E tests
# This script starts the API server and web frontend, then runs E2E tests

set -e

echo "Starting E2E Test Environment..."

# Check if API server is already running
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ API server already running"
    API_RUNNING=true
else
    echo "API server not running, will start it..."
    API_RUNNING=false
fi

# Check if web frontend is already running
if curl -sf http://localhost:5173 > /dev/null 2>&1; then
    echo "✓ Web frontend already running"
    WEB_RUNNING=true
else
    echo "Web frontend not running, will start it..."
    WEB_RUNNING=false
fi

# Start API server if not running
API_PID=""
if [ "$API_RUNNING" = false ]; then
    echo "Starting API server..."
    export DB_URL="sqlite:///./data/e2e.db"
    export ADMIN_EMAIL="admin@example.com"
    export ADMIN_PASSWORD="Admin@123"
    
    cd ..
    python -m uvicorn server.app.main:app --port 8000 > /dev/null 2>&1 &
    API_PID=$!
    cd web
    
    sleep 5
    
    # Verify API is running
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "✓ API server started successfully"
    else
        echo "✗ Failed to start API server"
        if [ -n "$API_PID" ]; then
            kill $API_PID 2>/dev/null || true
        fi
        exit 1
    fi
fi

# Start web frontend if not running
WEB_PID=""
if [ "$WEB_RUNNING" = false ]; then
    echo "Starting web frontend..."
    export VITE_API_URL="http://localhost:8000"
    
    npm run dev > /dev/null 2>&1 &
    WEB_PID=$!
    
    sleep 5
    
    # Verify web is running
    if curl -sf http://localhost:5173 > /dev/null 2>&1; then
        echo "✓ Web frontend started successfully"
    else
        echo "✗ Failed to start web frontend"
        if [ -n "$API_PID" ]; then
            kill $API_PID 2>/dev/null || true
        fi
        if [ -n "$WEB_PID" ]; then
            kill $WEB_PID 2>/dev/null || true
        fi
        exit 1
    fi
fi

# Install Playwright browsers if needed
echo "Checking Playwright browsers..."
npx playwright install chromium --quiet

# Run E2E tests
echo ""
echo "Running E2E tests..."
echo "========================================"

export PLAYWRIGHT_BASE_URL="http://localhost:5173"
npm run test:e2e
TEST_EXIT_CODE=$?

# Cleanup
echo ""
echo "Cleaning up..."
if [ -n "$API_PID" ] && [ "$API_RUNNING" = false ]; then
    kill $API_PID 2>/dev/null || true
    echo "✓ API server stopped"
fi

if [ -n "$WEB_PID" ] && [ "$WEB_RUNNING" = false ]; then
    kill $WEB_PID 2>/dev/null || true
    echo "✓ Web frontend stopped"
fi

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✓ All E2E tests passed!"
else
    echo ""
    echo "✗ Some E2E tests failed"
fi

exit $TEST_EXIT_CODE

