# Create Scheduled Tasks for Trading Bot
# Run as Administrator

$projectPath = "C:\Personal\Projects\TradingView\modular_trade_agent"
$python = "$projectPath\.venv\Scripts\python.exe"

Write-Host "Creating Scheduled Tasks..." -ForegroundColor Cyan
Write-Host ""

# Task 1: Analysis at 4:00 PM
$action1 = New-ScheduledTaskAction -Execute $python -Argument "trade_agent.py --backtest" -WorkingDirectory $projectPath
$trigger1 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 16:00
$settings1 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal1 = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest
Register-ScheduledTask -TaskName "TradingBot-Analysis" -Action $action1 -Trigger $trigger1 -Settings $settings1 -Principal $principal1 -Force
Write-Host "[OK] TradingBot-Analysis created (Mon-Fri 4:00 PM)" -ForegroundColor Green

# Task 2: Buy Orders at 4:05 PM
$action2 = New-ScheduledTaskAction -Execute $python -Argument "-m modules.kotak_neo_auto_trader.run_place_amo --env modules\kotak_neo_auto_trader\kotak_neo.env" -WorkingDirectory $projectPath
$trigger2 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 16:05
$settings2 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal2 = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest
Register-ScheduledTask -TaskName "TradingBot-BuyOrders" -Action $action2 -Trigger $trigger2 -Settings $settings2 -Principal $principal2 -Force
Write-Host "[OK] TradingBot-BuyOrders created (Mon-Fri 4:05 PM)" -ForegroundColor Green

# Task 3: Sell Monitor at 9:15 AM
$action3 = New-ScheduledTaskAction -Execute $python -Argument "-m modules.kotak_neo_auto_trader.run_sell_orders --env modules\kotak_neo_auto_trader\kotak_neo.env --monitor-interval 60" -WorkingDirectory $projectPath
$trigger3 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 09:15
$settings3 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 7)
$principal3 = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest
Register-ScheduledTask -TaskName "TradingBot-SellMonitor" -Action $action3 -Trigger $trigger3 -Settings $settings3 -Principal $principal3 -Force
Write-Host "[OK] TradingBot-SellMonitor created (Mon-Fri 9:15 AM)" -ForegroundColor Green

Write-Host ""
Write-Host "All tasks created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "To view tasks: taskschd.msc" -ForegroundColor Yellow
Write-Host "To check status: .\\manage_tasks.ps1 status" -ForegroundColor Yellow
