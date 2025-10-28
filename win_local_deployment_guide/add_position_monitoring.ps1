# Add Position Monitoring Task
# Run as Administrator

$projectPath = "C:\Personal\Projects\TradingView\modular_trade_agent"
$pythonExe = "$projectPath\.venv\Scripts\python.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "ADDING LIVE POSITION MONITORING TASK" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Verify python exists
if (-not (Test-Path $pythonExe)) {
    Write-Host "ERROR: Python executable not found at: $pythonExe" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Python executable found" -ForegroundColor Green
Write-Host ""

# Get current user
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
Write-Host "Creating task for user: $currentUser" -ForegroundColor Yellow
Write-Host ""

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName "TradingBot-PositionMonitor" -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName "TradingBot-PositionMonitor" -Confirm:$false
}

# Create action
$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "-m modules.kotak_neo_auto_trader.run_position_monitor" `
    -WorkingDirectory $projectPath

# Create trigger - Hourly from 9:30 AM to 3:30 PM, Mon-Fri
# We'll create a trigger that runs at 9:30 AM and repeats every hour for 7 hours
$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At 9:30AM

# Set repetition for hourly checks during market hours
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At 9:30AM -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Hours 6)).Repetition

# Create settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

# Create principal
$principal = New-ScheduledTaskPrincipal `
    -UserId $currentUser `
    -LogonType Interactive `
    -RunLevel Highest

# Register task
Register-ScheduledTask `
    -TaskName "TradingBot-PositionMonitor" `
    -Description "[Phase 3] Live position monitoring during market hours (9:30 AM - 3:30 PM)" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "[OK] Task created successfully!" -ForegroundColor Green
Write-Host ""

# Display task info
$task = Get-ScheduledTask -TaskName "TradingBot-PositionMonitor"
$info = Get-ScheduledTaskInfo -TaskName "TradingBot-PositionMonitor"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "TASK DETAILS" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Name: TradingBot-PositionMonitor" -ForegroundColor White
Write-Host "  State: $($task.State)" -ForegroundColor Green
Write-Host "  Next Run: $($info.NextRunTime)" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Schedule: Every hour from 9:30 AM to 3:30 PM" -ForegroundColor White
Write-Host "  Days: Monday - Friday" -ForegroundColor White
Write-Host "  Duration: ~15 minutes max per run" -ForegroundColor White
Write-Host ""
Write-Host "  Features:" -ForegroundColor Yellow
Write-Host "    • Monitors all open positions" -ForegroundColor White
Write-Host "    • Checks exit conditions (EMA9, RSI10>50)" -ForegroundColor White
Write-Host "    • Detects averaging opportunities (RSI10 < 20/10)" -ForegroundColor White
Write-Host "    • Tracks unrealized P&L" -ForegroundColor White
Write-Host "    • Sends Telegram alerts for:" -ForegroundColor White
Write-Host "      - Exit approaching (price near EMA9 or RSI near 50)" -ForegroundColor Gray
Write-Host "      - Large price movements (>3%)" -ForegroundColor Gray
Write-Host "      - Averaging opportunities" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "MANUAL TESTING" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Test the monitoring now:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName 'TradingBot-PositionMonitor'" -ForegroundColor White
Write-Host ""
Write-Host "Or run manually:" -ForegroundColor Yellow
Write-Host "  python -m modules.kotak_neo_auto_trader.run_position_monitor --force" -ForegroundColor White
Write-Host ""
Write-Host "Check logs:" -ForegroundColor Yellow
Write-Host "  Get-Content logs\*.log -Wait -Tail 50" -ForegroundColor White
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "IMPORTANT:" -ForegroundColor Red
Write-Host "  - Keep computer on during market hours (9:30 AM - 3:30 PM)" -ForegroundColor Red
Write-Host "  - Monitor Telegram for position alerts" -ForegroundColor Red
Write-Host "  - Task auto-skips outside market hours" -ForegroundColor Red
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
