#!/bin/bash
# Bash script to run E2E tests
# This script starts the API server and web frontend, then runs E2E tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

resolve_python() {
    if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
        echo "$PROJECT_ROOT/.venv/bin/python"
    elif [ -x "$PROJECT_ROOT/.venv/Scripts/python.exe" ]; then
        echo "$PROJECT_ROOT/.venv/Scripts/python.exe"
    else
        echo "python"
    fi
}

PYTHON="$(resolve_python)"
ENSURE_ADMIN_SCRIPT="$SCRIPT_DIR/tests/e2e/utils/ensure-test-admin.py"

# E2E environment (align with test-config.ts and security defaults)
export E2E_DB_URL="${E2E_DB_URL:-sqlite:///./data/e2e.db}"
export DB_URL="$E2E_DB_URL"
export ADMIN_EMAIL="${TEST_ADMIN_EMAIL:-testadmin@rebound.com}"
export ADMIN_PASSWORD="${TEST_ADMIN_PASSWORD:-testadmin@123}"
export ADMIN_NAME="${TEST_ADMIN_NAME:-Test Admin}"
export EMAIL_DOMAIN_ALLOWLIST_EXTRA="${EMAIL_DOMAIN_ALLOWLIST_EXTRA:-rebound.com}"
export E2E_SEED_DATA="${E2E_SEED_DATA:-true}"
export PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-http://localhost:5173}"
export VITE_API_URL="${VITE_API_URL:-http://localhost:8000}"

ensure_test_admin() {
    echo "Ensuring E2E test admin user..."
    "$PYTHON" "$ENSURE_ADMIN_SCRIPT"
    echo "✓ E2E test admin ready"
}

echo "Starting E2E Test Environment..."

# Check if API server is already running
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ API server already running"
    echo "  Tip: set E2E_DB_URL/DB_URL to match the running API database before ensure-test-admin."
    API_RUNNING=true
    ensure_test_admin
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
    cd "$PROJECT_ROOT"
    "$PYTHON" -m uvicorn server.app.main:app --port 8000 > /dev/null 2>&1 &
    API_PID=$!
    cd "$SCRIPT_DIR"

    sleep 5

    # Verify API is running
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "✓ API server started successfully"
        ensure_test_admin
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

    cd "$SCRIPT_DIR"
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
cd "$SCRIPT_DIR"
npx playwright install chromium --quiet

# Run E2E tests
echo ""
echo "Running E2E tests..."
echo "========================================"

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
