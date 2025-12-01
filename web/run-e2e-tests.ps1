# PowerShell script to run E2E tests
# This script starts the API server and web frontend, then runs E2E tests

Write-Host "Starting E2E Test Environment..." -ForegroundColor Cyan

# Check if API server is already running
$apiRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 2 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        $apiRunning = $true
        Write-Host "✓ API server already running" -ForegroundColor Green
    }
} catch {
    Write-Host "API server not running, will start it..." -ForegroundColor Yellow
}

# Check if web frontend is already running
$webRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 2 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        $webRunning = $true
        Write-Host "✓ Web frontend already running" -ForegroundColor Green
    }
} catch {
    Write-Host "Web frontend not running, will start it..." -ForegroundColor Yellow
}

# Start API server if not running
$apiProcess = $null
if (-not $apiRunning) {
    Write-Host "Starting API server..." -ForegroundColor Yellow
    $env:DB_URL = "sqlite:///./data/e2e.db"
    $env:ADMIN_EMAIL = "admin@example.com"
    $env:ADMIN_PASSWORD = "Admin@123"

    $apiProcess = Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "server.app.main:app", "--port", "8000" -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 5

    # Verify API is running
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 5
        Write-Host "✓ API server started successfully" -ForegroundColor Green
    } catch {
        Write-Host "✗ Failed to start API server" -ForegroundColor Red
        exit 1
    }
}

# Start web frontend if not running
$webProcess = $null
if (-not $webRunning) {
    Write-Host "Starting web frontend..." -ForegroundColor Yellow
    $env:VITE_API_URL = "http://localhost:8000"

    Push-Location $PSScriptRoot
    $webProcess = Start-Process -FilePath "npm" -ArgumentList "run", "dev" -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 5

    # Verify web is running
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 5
        Write-Host "✓ Web frontend started successfully" -ForegroundColor Green
    } catch {
        Write-Host "✗ Failed to start web frontend" -ForegroundColor Red
        if ($apiProcess) { Stop-Process -Id $apiProcess.Id -Force }
        exit 1
    }
    Pop-Location
}

# Install Playwright browsers if needed
Write-Host "Checking Playwright browsers..." -ForegroundColor Yellow
Push-Location $PSScriptRoot
npx playwright install chromium --quiet
Pop-Location

# Run E2E tests
Write-Host "`nRunning E2E tests..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Push-Location $PSScriptRoot
$env:PLAYWRIGHT_BASE_URL = "http://localhost:5173"
npm run test:e2e
$testExitCode = $LASTEXITCODE
Pop-Location

# Cleanup
Write-Host "`nCleaning up..." -ForegroundColor Yellow
if ($apiProcess -and -not $apiRunning) {
    Stop-Process -Id $apiProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "✓ API server stopped" -ForegroundColor Green
}

if ($webProcess -and -not $webRunning) {
    Stop-Process -Id $webProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "✓ Web frontend stopped" -ForegroundColor Green
}

if ($testExitCode -eq 0) {
    Write-Host "`n✓ All E2E tests passed!" -ForegroundColor Green
} else {
    Write-Host "`n✗ Some E2E tests failed" -ForegroundColor Red
}

exit $testExitCode
