# Manage Scheduled Trading Tasks
# Quick commands to control automated trading

param(
    [Parameter(Position=0)]
    [ValidateSet('status', 'enable', 'disable', 'test', 'logs', 'remove', 'help')]
    [string]$Action = 'status'
)

$tasks = @("TradingBot-Analysis", "TradingBot-BuyOrders", "TradingBot-SellMonitor")

function Show-Help {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "TRADING BOT TASK MANAGEMENT" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\manage_tasks.ps1 [action]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Actions:" -ForegroundColor Yellow
    Write-Host "  status   - Show status of all tasks (default)" -ForegroundColor White
    Write-Host "  enable   - Enable all tasks" -ForegroundColor White
    Write-Host "  disable  - Disable all tasks" -ForegroundColor White
    Write-Host "  test     - Run analysis task manually (test mode)" -ForegroundColor White
    Write-Host "  logs     - Show recent log entries" -ForegroundColor White
    Write-Host "  remove   - Remove all tasks" -ForegroundColor White
    Write-Host "  help     - Show this help message" -ForegroundColor White
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "  .\manage_tasks.ps1 status" -ForegroundColor Cyan
    Write-Host "  .\manage_tasks.ps1 disable" -ForegroundColor Cyan
    Write-Host "  .\manage_tasks.ps1 test" -ForegroundColor Cyan
    Write-Host ""
}

function Show-Status {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "TRADING BOT TASK STATUS" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host ""
    
    foreach ($taskName in $tasks) {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        
        if (-not $task) {
            Write-Host "  $taskName : NOT FOUND" -ForegroundColor Red
            continue
        }
        
        $info = Get-ScheduledTaskInfo -TaskName $taskName
        $state = $task.State
        $nextRun = $info.NextRunTime
        $lastRun = $info.LastRunTime
        $lastResult = $info.LastTaskResult
        
        # Color based on state
        $stateColor = switch ($state) {
            "Ready" { "Green" }
            "Running" { "Yellow" }
            "Disabled" { "Gray" }
            default { "White" }
        }
        
        Write-Host "  Task: $taskName" -ForegroundColor Cyan
        Write-Host "    State       : $state" -ForegroundColor $stateColor
        Write-Host "    Next Run    : $nextRun" -ForegroundColor White
        Write-Host "    Last Run    : $lastRun" -ForegroundColor White
        
        if ($lastResult -eq 0) {
            Write-Host "    Last Result : Success (0)" -ForegroundColor Green
        } else {
            Write-Host "    Last Result : $lastResult" -ForegroundColor Red
        }
        Write-Host ""
    }
    
    Write-Host "===========================================================" -ForegroundColor Cyan
}

function Enable-Tasks {
    Write-Host ""
    Write-Host "Enabling all trading tasks..." -ForegroundColor Yellow
    foreach ($taskName in $tasks) {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($task) {
            Enable-ScheduledTask -TaskName $taskName | Out-Null
            Write-Host "  [OK] $taskName enabled" -ForegroundColor Green
        } else {
            Write-Host "  [X] $taskName not found" -ForegroundColor Red
        }
    }
    Write-Host ""
    Write-Host "All tasks enabled!" -ForegroundColor Green
    Write-Host ""
}

function Disable-Tasks {
    Write-Host ""
    Write-Host "Disabling all trading tasks..." -ForegroundColor Yellow
    foreach ($taskName in $tasks) {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($task) {
            Disable-ScheduledTask -TaskName $taskName | Out-Null
            Write-Host "  [OK] $taskName disabled" -ForegroundColor Green
        } else {
            Write-Host "  [X] $taskName not found" -ForegroundColor Red
        }
    }
    Write-Host ""
    Write-Host "All tasks disabled!" -ForegroundColor Green
    Write-Host ""
}

function Test-AnalysisTask {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "TESTING ANALYSIS TASK" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Starting analysis task manually..." -ForegroundColor Yellow
    Write-Host "This will take 5-15 minutes. Press Ctrl+C to cancel." -ForegroundColor Yellow
    Write-Host ""
    
    Start-ScheduledTask -TaskName "TradingBot-Analysis"
    
    Write-Host "Task started. Monitoring status..." -ForegroundColor Yellow
    Write-Host ""
    
    # Wait and show status
    for ($i = 1; $i -le 30; $i++) {
        Start-Sleep -Seconds 2
        $task = Get-ScheduledTask -TaskName "TradingBot-Analysis"
        $state = $task.State
        
        Write-Host "`rStatus: $state (checking $i/30)..." -NoNewline
        
        if ($state -eq "Ready") {
            Write-Host ""
            Write-Host ""
            Write-Host "[OK] Task completed!" -ForegroundColor Green
            
            $info = Get-ScheduledTaskInfo -TaskName "TradingBot-Analysis"
            if ($info.LastTaskResult -eq 0) {
                Write-Host "[OK] Task result: Success" -ForegroundColor Green
            } else {
                Write-Host "[ERROR] Task result: $($info.LastTaskResult)" -ForegroundColor Red
            }
            Write-Host ""
            
            # Show recent logs
            $logFile = "logs\trade_agent.log"
            if (Test-Path $logFile) {
                Write-Host "Recent log entries:" -ForegroundColor Yellow
                Get-Content $logFile -Tail 20
            }
            
            # Show recent CSV
            $csvFiles = Get-ChildItem "analysis_results\bulk_analysis_final_*.csv" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
            if ($csvFiles) {
                Write-Host ""
                Write-Host "Latest analysis CSV: $($csvFiles[0].Name)" -ForegroundColor Cyan
            }
            
            break
        }
    }
    
    if ($task.State -eq "Running") {
        Write-Host ""
        Write-Host ""
        Write-Host "Task is still running. Check logs for progress:" -ForegroundColor Yellow
        Write-Host "  Get-Content logs\trade_agent.log -Wait -Tail 50" -ForegroundColor White
    }
    
    Write-Host ""
}

function Show-Logs {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "RECENT LOG ENTRIES" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host ""
    
    $logFile = "logs\trade_agent.log"
    if (Test-Path $logFile) {
        Get-Content $logFile -Tail 50
    } else {
        Write-Host "Log file not found: $logFile" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "To monitor logs in real-time:" -ForegroundColor Yellow
    Write-Host "  Get-Content logs\trade_agent.log -Wait -Tail 50" -ForegroundColor White
    Write-Host ""
}

function Remove-Tasks {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Red
    Write-Host "WARNING: REMOVING ALL TASKS" -ForegroundColor Red
    Write-Host "===========================================================" -ForegroundColor Red
    Write-Host ""
    
    $confirm = Read-Host "Are you sure you want to remove all trading tasks? (yes/no)"
    
    if ($confirm -eq "yes") {
        foreach ($taskName in $tasks) {
            $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
            if ($task) {
                Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
                Write-Host "  [OK] $taskName removed" -ForegroundColor Green
            } 
            else {
                Write-Host "  - $taskName not found" -ForegroundColor Gray
            }
        }
        Write-Host ""
        Write-Host "All tasks removed!" -ForegroundColor Green
    } else {
        Write-Host "Cancelled." -ForegroundColor Yellow
    }
    
    Write-Host ""
}

# Main execution
switch ($Action) {
    'status'  { Show-Status }
    'enable'  { Enable-Tasks; Show-Status }
    'disable' { Disable-Tasks; Show-Status }
    'test'    { Test-AnalysisTask }
    'logs'    { Show-Logs }
    'remove'  { Remove-Tasks }
    'help'    { Show-Help }
    default   { Show-Help }
}
