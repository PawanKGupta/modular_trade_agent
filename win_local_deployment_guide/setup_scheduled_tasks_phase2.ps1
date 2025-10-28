# Setup Scheduled Tasks for Automated Trading System (Phase 1 & 2 Complete)
# Run this script as Administrator

$projectPath = "C:\Personal\Projects\TradingView\modular_trade_agent"
$pythonExe = "$projectPath\.venv\Scripts\python.exe"
$envFile = "$projectPath\modules\kotak_neo_auto_trader\kotak_neo.env"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "AUTOMATED TRADING SYSTEM - PHASE 1 & 2 TASK SETUP" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Verify paths exist
if (-not (Test-Path $pythonExe)) {
    Write-Host "ERROR: Python executable not found at: $pythonExe" -ForegroundColor Red
    Write-Host "Please verify your virtual environment is set up correctly." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: Environment file not found at: $envFile" -ForegroundColor Red
    Write-Host "Please create the kotak_neo.env file with your credentials." -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Python executable found" -ForegroundColor Green
Write-Host "[OK] Environment file found" -ForegroundColor Green
Write-Host ""

# Get current user
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
Write-Host "Creating tasks for user: $currentUser" -ForegroundColor Yellow
Write-Host ""

# Function to create or update scheduled task
function Create-TradingTask {
    param(
        [string]$TaskName,
        [string]$Description,
        [string]$Arguments,
        [string]$Time,
        [int]$DurationHours = 1
    )
    
    Write-Host "Creating task: $TaskName" -ForegroundColor Cyan
    
    # Remove existing task if it exists
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-Host "  - Removing existing task..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    
    # Create action
    $action = New-ScheduledTaskAction `
        -Execute $pythonExe `
        -Argument $Arguments `
        -WorkingDirectory $projectPath
    
    # Create trigger (Mon-Fri at specified time)
    $trigger = New-ScheduledTaskTrigger `
        -Weekly `
        -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
        -At $Time
    
    # Create settings
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 5) `
        -ExecutionTimeLimit (New-TimeSpan -Hours $DurationHours)
    
    # Create principal (run with highest privileges)
    $principal = New-ScheduledTaskPrincipal `
        -UserId $currentUser `
        -LogonType Interactive `
        -RunLevel Highest
    
    # Register task
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $Description `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Force | Out-Null
    
    Write-Host "  [OK] Task created successfully" -ForegroundColor Green
    Write-Host ""
}

# =============================================================================
# PHASE 1 & 2 TASKS
# =============================================================================

# Task 1: Daily Analysis (4:00 PM)
Create-TradingTask `
    -TaskName "TradingBot-Analysis" `
    -Description "Daily stock analysis at 4:00 PM with backtest scoring" `
    -Arguments "trade_agent.py --backtest" `
    -Time "16:00" `
    -DurationHours 1

# Task 2: Place AMO Orders (4:05 PM)
# Phase 1: Tracking scope + Order tracker active
# Phase 2: Order verifier runs in background (30-min checks)
Create-TradingTask `
    -TaskName "TradingBot-PlaceOrders" `
    -Description "[Phase 1 & 2] Place AMO orders with tracking and auto-verification" `
    -Arguments "-m modules.kotak_neo_auto_trader.run_place_amo --env modules\kotak_neo_auto_trader\kotak_neo.env" `
    -Time "16:05" `
    -DurationHours 1

# Task 3: Pre-Market Retry (8:00 AM)
# Retry any failed orders from previous day
Create-TradingTask `
    -TaskName "TradingBot-PreMarketRetry" `
    -Description "[Phase 1 & 2] Retry failed AMO orders before market opens" `
    -Arguments "-m modules.kotak_neo_auto_trader.run_place_amo --env modules\kotak_neo_auto_trader\kotak_neo.env" `
    -Time "08:00" `
    -DurationHours 1

# Task 4: EOD Cleanup (6:00 PM)
# Phase 2: End-of-day reconciliation, manual trade detection, statistics
Create-TradingTask `
    -TaskName "TradingBot-EODCleanup" `
    -Description "[Phase 2] End-of-day cleanup: reconciliation, manual trades, stats, Telegram summary" `
    -Arguments "-m modules.kotak_neo_auto_trader.run_eod_cleanup --env modules\kotak_neo_auto_trader\kotak_neo.env" `
    -Time "18:00" `
    -DurationHours 1

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "PHASE 1 & 2 SETUP COMPLETE!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Scheduled Tasks Created:" -ForegroundColor Yellow
Write-Host "  1. TradingBot-Analysis       (Mon-Fri at 4:00 PM)" -ForegroundColor White
Write-Host "     -> Analyze stocks and generate recommendations" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. TradingBot-PlaceOrders    (Mon-Fri at 4:05 PM) [Phase 1 and 2]" -ForegroundColor White
Write-Host "     -> Place AMO orders with tracking" -ForegroundColor Gray
Write-Host "     -> Order verifier runs automatically (30-min intervals)" -ForegroundColor Gray
Write-Host "     -> Telegram notifications on execution/rejection" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. TradingBot-PreMarketRetry (Mon-Fri at 8:00 AM)" -ForegroundColor White
Write-Host "     -> Retry failed orders from previous day" -ForegroundColor Gray
Write-Host ""
Write-Host "  4. TradingBot-EODCleanup     (Mon-Fri at 6:00 PM) [Phase 2]" -ForegroundColor Cyan
Write-Host "     -> Final order verification" -ForegroundColor Gray
Write-Host "     -> Manual trade reconciliation" -ForegroundColor Gray
Write-Host "     -> Stale order cleanup" -ForegroundColor Gray
Write-Host "     -> Daily statistics generation" -ForegroundColor Gray
Write-Host "     -> Telegram daily summary" -ForegroundColor Gray
Write-Host "     -> Archive completed entries" -ForegroundColor Gray
Write-Host ""

# Display next run times
Write-Host "Next Scheduled Runs:" -ForegroundColor Yellow
$tasks = @("TradingBot-Analysis", "TradingBot-PlaceOrders", "TradingBot-PreMarketRetry", "TradingBot-EODCleanup")
foreach ($taskName in $tasks) {
    $task = Get-ScheduledTask -TaskName $taskName
    $info = Get-ScheduledTaskInfo -TaskName $taskName
    $nextRun = $info.NextRunTime
    Write-Host "  $taskName : $nextRun" -ForegroundColor Cyan
}
Write-Host ""

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "PHASE 2 FEATURES ACTIVE:" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  [OK] Automatic order tracking (Phase 1)" -ForegroundColor Green
Write-Host "  [OK] Order ID extraction with fallback (Phase 1)" -ForegroundColor Green
Write-Host "  [OK] Pending order management (Phase 1)" -ForegroundColor Green
Write-Host "  [OK] Trade reconciliation (Phase 1)" -ForegroundColor Green
Write-Host "  [OK] Order status verifier (30-min checks) (Phase 2)" -ForegroundColor Green
Write-Host "  [OK] Telegram notifications (Phase 2)" -ForegroundColor Green
Write-Host "  [OK] Manual trade detection (Phase 2)" -ForegroundColor Green
Write-Host "  [OK] EOD cleanup workflow (Phase 2)" -ForegroundColor Green
Write-Host ""

Write-Host "To view tasks in Task Scheduler GUI: taskschd.msc" -ForegroundColor Yellow
Write-Host "To manage tasks: .\manage_tasks.ps1 status" -ForegroundColor Yellow
Write-Host ""
Write-Host "IMPORTANT:" -ForegroundColor Red
Write-Host "  - Keep your computer on during scheduled times" -ForegroundColor Red
Write-Host "  - Ensure Telegram bot token and chat ID are configured" -ForegroundColor Red
Write-Host "  - Monitor Telegram for order notifications" -ForegroundColor Red
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
