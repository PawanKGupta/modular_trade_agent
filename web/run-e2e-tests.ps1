# PowerShell script to run E2E tests
# This script starts the API server and web frontend, then runs E2E tests

Write-Host "Starting E2E Test Environment..." -ForegroundColor Cyan

# Get project root for scripts
$projectRoot = Split-Path -Parent $PSScriptRoot

# Check if API server is already running
$apiRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 2 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        $apiRunning = $true
        Write-Host "[OK] API server already running" -ForegroundColor Green

        # Ensure test admin user exists (even if API server is already running)
        Write-Host "Ensuring test admin user exists..." -ForegroundColor Yellow
        try {
            # Try to find Python
            $pythonExe = $null
            if (Test-Path "$projectRoot\.venv\Scripts\python.exe") {
                $pythonExe = "$projectRoot\.venv\Scripts\python.exe"
            } elseif ($env:VIRTUAL_ENV -and (Test-Path "$env:VIRTUAL_ENV\Scripts\python.exe")) {
                $pythonExe = "$env:VIRTUAL_ENV\Scripts\python.exe"
            } else {
                $pythonExe = (Get-Command python -ErrorAction Stop).Source
            }

            if ($pythonExe) {
                Push-Location $projectRoot
                $ensureAdminScript = Join-Path $PSScriptRoot "tests\e2e\utils\ensure-test-admin.py"
                & $pythonExe $ensureAdminScript 2>&1 | Out-Null
                Pop-Location
            }
        } catch {
            Write-Host "[WARNING] Could not verify test admin user exists" -ForegroundColor Yellow
        }
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
        Write-Host "[OK] Web frontend already running" -ForegroundColor Green
    }
} catch {
    Write-Host "Web frontend not running, will start it..." -ForegroundColor Yellow
}

# Start API server if not running
$apiProcess = $null
if (-not $apiRunning) {
    Write-Host "Starting API server..." -ForegroundColor Yellow

    # Try to find Python - prefer virtual environment, fallback to PATH
    $pythonExe = $null

    # Check if virtual environment is in project root
    if (Test-Path "$projectRoot\.venv\Scripts\python.exe") {
        $pythonExe = "$projectRoot\.venv\Scripts\python.exe"
        Write-Host "Using virtual environment Python: $pythonExe" -ForegroundColor Gray
    }
    # Check if python in PATH is from a venv (common when venv is activated)
    elseif ($env:VIRTUAL_ENV -and (Test-Path "$env:VIRTUAL_ENV\Scripts\python.exe")) {
        $pythonExe = "$env:VIRTUAL_ENV\Scripts\python.exe"
        Write-Host "Using activated virtual environment Python: $pythonExe" -ForegroundColor Gray
    }
    # Try to find python in PATH
    else {
        try {
            $pythonExe = (Get-Command python -ErrorAction Stop).Source
            Write-Host "Using Python from PATH: $pythonExe" -ForegroundColor Gray
        } catch {
            Write-Host "[ERROR] Python not found. Please:" -ForegroundColor Red
            Write-Host "  1. Activate your virtual environment: .venv\Scripts\Activate.ps1" -ForegroundColor Yellow
            Write-Host "  2. Or ensure Python is in your PATH" -ForegroundColor Yellow
            exit 1
        }
    }

    # Set environment variables for the API server
    # IMPORTANT: Use test admin credentials that match test-config.ts
    $env:DB_URL = "sqlite:///./data/e2e.db"
    $env:ADMIN_EMAIL = $env:TEST_ADMIN_EMAIL
    if (-not $env:ADMIN_EMAIL) {
        $env:ADMIN_EMAIL = "testadmin@rebound.com"
    }
    $env:ADMIN_PASSWORD = $env:TEST_ADMIN_PASSWORD
    if (-not $env:ADMIN_PASSWORD) {
        $env:ADMIN_PASSWORD = "testadmin@123"
    }
    $env:ADMIN_NAME = $env:TEST_ADMIN_NAME
    if (-not $env:ADMIN_NAME) {
        $env:ADMIN_NAME = "Test Admin"
    }

    # Start API server from project root directory (uvicorn needs to run from project root)
    Write-Host "Starting API server from project root: $projectRoot" -ForegroundColor Gray
    Push-Location $projectRoot
    try {
        $apiProcess = Start-Process -FilePath $pythonExe -ArgumentList "-m", "uvicorn", "server.app.main:app", "--port", "8000" -PassThru -WindowStyle Hidden
    } finally {
        Pop-Location
    }

    # Wait for server to start and verify it's running
    Start-Sleep -Seconds 8

    # Verify API is running (try a few times)
    $maxRetries = 5
    $retryCount = 0
    $apiStarted = $false

    while ($retryCount -lt $maxRetries -and -not $apiStarted) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 5 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                $apiStarted = $true
                Write-Host "[OK] API server started successfully" -ForegroundColor Green
            }
        } catch {
            $retryCount++
            if ($retryCount -lt $maxRetries) {
                Write-Host "Waiting for API server... (attempt $retryCount/$maxRetries)" -ForegroundColor Yellow
                Start-Sleep -Seconds 2
            }
        }
    }

    # After API server is confirmed running, ensure test admin user exists
    if ($apiStarted) {
        Write-Host "Ensuring test admin user exists..." -ForegroundColor Yellow
        try {
            Push-Location $projectRoot
            $ensureAdminScript = Join-Path $PSScriptRoot "tests\e2e\utils\ensure-test-admin.py"
            & $pythonExe $ensureAdminScript 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[OK] Test admin user verified" -ForegroundColor Green
            } else {
                Write-Host "[WARNING] Failed to ensure test admin user. Tests may fail." -ForegroundColor Yellow
            }
            Pop-Location
        } catch {
            Write-Host "[WARNING] Could not ensure test admin user: $_" -ForegroundColor Yellow
            if ((Get-Location).Path -ne $PSScriptRoot) {
                Pop-Location
            }
        }
    }

    if (-not $apiStarted) {
        Write-Host "[ERROR] Failed to start API server after $maxRetries attempts" -ForegroundColor Red
        Write-Host "" -ForegroundColor Red
        Write-Host "Troubleshooting steps:" -ForegroundColor Yellow
        Write-Host "  1. Check if port 8000 is already in use:" -ForegroundColor Yellow
        Write-Host "     netstat -ano | findstr :8000" -ForegroundColor Gray
        Write-Host "  2. Try starting the API server manually to see errors:" -ForegroundColor Yellow
        Write-Host "     cd .." -ForegroundColor Gray
        Write-Host "     `$env:DB_URL='sqlite:///./data/e2e.db'" -ForegroundColor Gray
        Write-Host "     $pythonExe -m uvicorn server.app.main:app --port 8000" -ForegroundColor Gray
        Write-Host "  3. Check if all dependencies are installed in your virtual environment" -ForegroundColor Yellow
        Write-Host "  4. Verify the database directory exists: Test-Path ..\data" -ForegroundColor Yellow
        Write-Host "" -ForegroundColor Red

        # Try to check if process is still running
        if ($apiProcess) {
            try {
                $proc = Get-Process -Id $apiProcess.Id -ErrorAction Stop
                Write-Host "API process is still running (PID: $($apiProcess.Id)). Stopping..." -ForegroundColor Yellow
                Stop-Process -Id $apiProcess.Id -Force -ErrorAction SilentlyContinue
            } catch {
                Write-Host "API process already terminated or not found" -ForegroundColor Yellow
            }
        }
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
        Write-Host "[OK] Web frontend started successfully" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] Failed to start web frontend" -ForegroundColor Red
        if ($apiProcess) { Stop-Process -Id $apiProcess.Id -Force }
        exit 1
    }
    Pop-Location
}

# Install Playwright browsers if needed
Write-Host "Checking Playwright browsers..." -ForegroundColor Yellow
Push-Location $PSScriptRoot
npx playwright install chromium 2>&1 | Out-Null
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
    Write-Host "[OK] API server stopped" -ForegroundColor Green
}

if ($webProcess -and -not $webRunning) {
    Stop-Process -Id $webProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] Web frontend stopped" -ForegroundColor Green
}

if ($testExitCode -eq 0) {
    Write-Host "`n[OK] All E2E tests passed!" -ForegroundColor Green
} else {
    Write-Host "`n[ERROR] Some E2E tests failed" -ForegroundColor Red
}

exit $testExitCode
