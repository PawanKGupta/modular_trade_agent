# Setup Scheduled Tasks for Automated Trading System
# Run this script as Administrator

$projectPath = "C:\Personal\Projects\TradingView\modular_trade_agent"
$pythonExe = "$projectPath\.venv\Scripts\python.exe"
$envFile = "$projectPath\modules\kotak_neo_auto_trader\kotak_neo.env"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "AUTOMATED TRADING SYSTEM - TASK SCHEDULER SETUP" -ForegroundColor Cyan
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

# Task 1: Analysis (4:00 PM)
Create-TradingTask `
    -TaskName "TradingBot-Analysis" `
    -Description "Daily stock analysis at 4:00 PM with backtest scoring" `
    -Arguments "trade_agent.py --backtest" `
    -Time "16:00" `
    -DurationHours 1

# Task 2: Buy Orders (4:05 PM)
Create-TradingTask `
    -TaskName "TradingBot-BuyOrders" `
    -Description "Place AMO buy orders at 4:05 PM based on analysis" `
    -Arguments "-m modules.kotak_neo_auto_trader.run_place_amo --env modules\kotak_neo_auto_trader\kotak_neo.env" `
    -Time "16:05" `
    -DurationHours 1

# Task 2b: Pre-Market Retry (8:00 AM)
Create-TradingTask `
    -TaskName "TradingBot-PreMarketRetry" `
    -Description "Retry failed AMO orders at 8:00 AM (before market opens)" `
    -Arguments "-m modules.kotak_neo_auto_trader.run_place_amo --env modules\kotak_neo_auto_trader\kotak_neo.env" `
    -Time "08:00" `
    -DurationHours 1

# Task 3: Sell Monitoring (9:15 AM)
Create-TradingTask `
    -TaskName "TradingBot-SellMonitor" `
    -Description "Monitor holdings and place sell orders (9:15 AM - 3:30 PM)" `
    -Arguments "-m modules.kotak_neo_auto_trader.run_sell_orders --env modules\kotak_neo_auto_trader\kotak_neo.env --monitor-interval 60" `
    -Time "09:15" `
    -DurationHours 7

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "SETUP COMPLETE!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Scheduled Tasks Created:" -ForegroundColor Yellow
Write-Host "  1. TradingBot-Analysis        (Mon-Fri at 4:00 PM)" -ForegroundColor White
Write-Host "  2. TradingBot-BuyOrders       (Mon-Fri at 4:05 PM)" -ForegroundColor White
Write-Host "  3. TradingBot-PreMarketRetry  (Mon-Fri at 8:00 AM) <- RETRY FAILED ORDERS" -ForegroundColor Cyan
Write-Host "  4. TradingBot-SellMonitor     (Mon-Fri at 9:15 AM)" -ForegroundColor White
Write-Host ""

# Display next run times
Write-Host "Next Scheduled Runs:" -ForegroundColor Yellow
$tasks = @("TradingBot-Analysis", "TradingBot-BuyOrders", "TradingBot-PreMarketRetry", "TradingBot-SellMonitor")
foreach ($taskName in $tasks) {
    $task = Get-ScheduledTask -TaskName $taskName
    $info = Get-ScheduledTaskInfo -TaskName $taskName
    $nextRun = $info.NextRunTime
    Write-Host "  $taskName : $nextRun" -ForegroundColor Cyan
}
Write-Host ""

Write-Host "To view tasks in Task Scheduler GUI, run: taskschd.msc" -ForegroundColor Yellow
Write-Host ""
Write-Host "To manually test a task, run:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName 'TradingBot-Analysis'" -ForegroundColor White
Write-Host ""
Write-Host "To disable a task, run:" -ForegroundColor Yellow
Write-Host "  Disable-ScheduledTask -TaskName 'TradingBot-Analysis'" -ForegroundColor White
Write-Host ""
Write-Host "IMPORTANT: Keep your computer on during scheduled times!" -ForegroundColor Red
Write-Host "============================================================" -ForegroundColor Cyan
