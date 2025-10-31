# Configure Trading Service for Continuous 24/7 Operation
# Run as Administrator

Write-Host "Configuring TradingService-Unified for continuous operation..." -ForegroundColor Yellow

# Delete existing task
Unregister-ScheduledTask -TaskName "TradingService-Unified" -Confirm:$false -ErrorAction SilentlyContinue

# Create new task with continuous settings
$projectPath = "C:\Personal\Projects\TradingView\modular_trade_agent"
$pythonExe = "$projectPath\.venv\Scripts\python.exe"

$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "-m modules.kotak_neo_auto_trader.run_trading_service --env modules/kotak_neo_auto_trader/kotak_neo.env" `
    -WorkingDirectory $projectPath

# Trigger: At system startup
$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -Priority 4

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName "TradingService-Unified" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Unified Trading Service - Runs continuously 24/7. Tasks execute automatically on trading days (Mon-Fri). Single login session maintained." `
    -Force | Out-Null

Write-Host "✓ Task configured for continuous operation" -ForegroundColor Green
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  • Trigger: At system startup" -ForegroundColor White
Write-Host "  • Timeout: Infinite (PT0S)" -ForegroundColor White
Write-Host "  • Auto-restart: Yes (3 attempts, 5 min interval)" -ForegroundColor White
Write-Host "  • Mode: Continuous 24/7" -ForegroundColor White
Write-Host ""
Write-Host "To start now:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName 'TradingService-Unified'" -ForegroundColor White
Write-Host ""
Write-Host "To stop:" -ForegroundColor Yellow
Write-Host "  Stop-ScheduledTask -TaskName 'TradingService-Unified'" -ForegroundColor White
