# Create Portable Python Package with All Dependencies
# This creates a complete, standalone Python environment that can be distributed

param(
    [string]$OutputDir = "portable_package",
    [string]$PythonVersion = "3.11.0"
)

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Creating Portable Python Package" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create output directory
Write-Host "[1/6] Creating output directory..." -ForegroundColor Green
if (Test-Path $OutputDir) {
    Remove-Item -Recurse -Force $OutputDir
}
New-Item -ItemType Directory -Path $OutputDir | Out-Null

# Step 2: Download Python embeddable package
Write-Host "[2/6] Downloading Python embeddable package..." -ForegroundColor Green
$pythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$pythonZip = "$OutputDir\python-embed.zip"

try {
    Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonZip
    Write-Host "  Downloaded Python $PythonVersion" -ForegroundColor White
} catch {
    Write-Host "  ERROR: Failed to download Python!" -ForegroundColor Red
    Write-Host "  URL: $pythonUrl" -ForegroundColor Yellow
    exit 1
}

# Step 3: Extract Python
Write-Host "[3/6] Extracting Python..." -ForegroundColor Green
$pythonDir = "$OutputDir\python"
Expand-Archive -Path $pythonZip -DestinationPath $pythonDir -Force
Remove-Item $pythonZip

# Step 4: Enable pip in embedded Python
Write-Host "[4/6] Configuring embedded Python for pip..." -ForegroundColor Green
$pthFile = Get-ChildItem -Path $pythonDir -Filter "python*._pth" | Select-Object -First 1
if ($pthFile) {
    # Uncomment the import site line to enable pip
    $content = Get-Content $pthFile.FullName
    $content = $content -replace '#import site', 'import site'
    $content | Set-Content $pthFile.FullName
    Write-Host "  Enabled site packages" -ForegroundColor White
}

# Step 5: Install pip
Write-Host "[5/6] Installing pip..." -ForegroundColor Green
$getpipUrl = "https://bootstrap.pypa.io/get-pip.py"
$getpipPath = "$pythonDir\get-pip.py"
Invoke-WebRequest -Uri $getpipUrl -OutFile $getpipPath

& "$pythonDir\python.exe" $getpipPath
Remove-Item $getpipPath

# Step 6: Install project dependencies
Write-Host "[6/6] Installing project dependencies..." -ForegroundColor Green
Write-Host "  This may take 5-10 minutes..." -ForegroundColor Yellow

if (Test-Path "requirements.txt") {
    & "$pythonDir\python.exe" -m pip install -r requirements.txt --no-warn-script-location
} else {
    Write-Host "  WARNING: requirements.txt not found!" -ForegroundColor Yellow
    Write-Host "  Installing common dependencies..." -ForegroundColor Yellow
    
    $dependencies = @(
        "pandas",
        "numpy",
        "yfinance",
        "requests",
        "ta",
        "pyotp",
        "neo-api-client",
        "selenium",
        "webdriver-manager",
        "schedule",
        "python-dotenv"
    )
    
    foreach ($dep in $dependencies) {
        Write-Host "    Installing $dep..." -ForegroundColor Gray
        & "$pythonDir\python.exe" -m pip install $dep --no-warn-script-location
    }
}

# Step 7: Copy project files
Write-Host "[7/7] Copying project files..." -ForegroundColor Green
$projectDir = "$OutputDir\TradingAgent"
New-Item -ItemType Directory -Path $projectDir | Out-Null

# Copy essential project files
$filesToCopy = @(
    "modules",
    "core",
    "config",
    "utils",
    "documents",
    "data",
    "README.md",
    "kotak_neo.env.example"
)

foreach ($item in $filesToCopy) {
    if (Test-Path $item) {
        Copy-Item -Path $item -Destination $projectDir -Recurse -Force
        Write-Host "  Copied: $item" -ForegroundColor White
    }
}

# Step 8: Create launcher scripts
Write-Host "[8/8] Creating launcher scripts..." -ForegroundColor Green

# Create run.bat
$runBatContent = @"
@echo off
REM Portable Python Launcher for Trading Agent
REM No Python installation required on the system!

echo =====================================
echo Modular Trade Agent (Portable)
echo =====================================
echo.

REM Set Python path to bundled Python
set PYTHONPATH=%~dp0TradingAgent
set PATH=%~dp0python;%PATH%

REM Check if Python exists
if not exist "%~dp0python\python.exe" (
    echo ERROR: Bundled Python not found!
    pause
    exit /b 1
)

REM Check if env file exists
if not exist "%~dp0TradingAgent\kotak_neo.env" (
    echo WARNING: kotak_neo.env not found!
    echo Please copy kotak_neo.env.example to kotak_neo.env and configure it.
    echo.
    pause
    exit /b 1
)

echo Starting Trading Agent...
echo.

REM Run the main script
cd /d "%~dp0TradingAgent"
"%~dp0python\python.exe" modules\kotak_neo_auto_trader\run_auto_trade.py

echo.
echo Agent stopped.
pause
"@
$runBatContent | Out-File -FilePath "$OutputDir\RUN_AGENT.bat" -Encoding ASCII

# Create install_dependencies.bat
$installDepsContent = @"
@echo off
REM Install/Update Dependencies

echo =====================================
echo Installing/Updating Dependencies
echo =====================================
echo.

set PATH=%~dp0python;%PATH%

if not exist "%~dp0TradingAgent\requirements.txt" (
    echo ERROR: requirements.txt not found!
    pause
    exit /b 1
)

cd /d "%~dp0TradingAgent"
"%~dp0python\python.exe" -m pip install -r requirements.txt --upgrade

echo.
echo Dependencies updated!
pause
"@
$installDepsContent | Out-File -FilePath "$OutputDir\UPDATE_DEPENDENCIES.bat" -Encoding ASCII

# Create README for portable package
$portableReadme = @"
# Modular Trade Agent - Portable Package

## What's Included

This is a **completely portable** package that includes:
- ✅ Python $PythonVersion (embedded)
- ✅ All required dependencies pre-installed
- ✅ Complete Trading Agent source code
- ✅ No installation required!

## Quick Start

1. **Extract this folder** anywhere on your PC (e.g., D:\TradingAgent)

2. **Configure credentials**:
   - Navigate to TradingAgent folder
   - Copy kotak_neo.env.example to kotak_neo.env
   - Edit kotak_neo.env with your credentials

3. **Run the agent**:
   - Double-click RUN_AGENT.bat
   - That's it!

## Folder Structure

```
portable_package/
  ├── python/                     # Embedded Python $PythonVersion
  │   ├── python.exe
  │   ├── Lib/
  │   └── Scripts/
  ├── TradingAgent/              # Your trading application
  │   ├── modules/
  │   ├── core/
  │   ├── config/
  │   ├── data/
  │   └── kotak_neo.env.example
  ├── RUN_AGENT.bat              # Main launcher
  ├── UPDATE_DEPENDENCIES.bat    # Update Python packages
  └── README.md                  # This file
```

## Features

✅ **No System Python Required** - Everything is self-contained
✅ **Portable** - Copy to any PC and run
✅ **No Admin Rights Required** - Runs from user folder
✅ **Editable** - Modify Python scripts directly
✅ **Easy Updates** - Just replace files

## System Requirements

- Windows 10/11 (64-bit)
- 500 MB disk space
- Internet connection (for trading API)

## Updating the Application

### Update Python Dependencies
1. Run UPDATE_DEPENDENCIES.bat

### Update Trading Agent Code
1. Replace files in TradingAgent folder
2. Keep your kotak_neo.env file

### Update Python Version
1. Download new portable package
2. Copy your TradingAgent\kotak_neo.env
3. Copy your TradingAgent\data folder

## Running as Scheduled Task

1. Open Task Scheduler
2. Create Basic Task:
   - Name: Trading Agent
   - Trigger: Daily at 8:00 AM
   - Action: Start program
   - Program: C:\path\to\RUN_AGENT.bat
   - Start in: C:\path\to\portable_package

## Troubleshooting

### Python not found
- Check that python\python.exe exists
- Don't move/rename the python folder

### Dependencies missing
- Run UPDATE_DEPENDENCIES.bat
- Check internet connection

### Script errors
- Check kotak_neo.env is configured
- View logs in console output
- Check data folder permissions

## Advantages vs. Compiled .exe

| Feature | Portable Python | Compiled .exe |
|---------|----------------|---------------|
| File Size | Larger (~200MB) | Smaller (~50MB) |
| Startup Speed | Fast | Slower (extracts) |
| Editability | ✅ Can modify code | ❌ Compiled |
| Debugging | ✅ Full stack traces | ❌ Limited |
| Updates | Easy (replace files) | Full rebuild |

## Support

Check console output for errors and refer to:
- TradingAgent\documents\*.md for documentation
- TradingAgent\README.md for project info

Happy Trading! 🚀
"@
$portableReadme | Out-File -FilePath "$OutputDir\README.md" -Encoding UTF8

# Final summary
Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "Portable Package Created!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "Location: $OutputDir" -ForegroundColor Cyan
Write-Host ""

$packageSize = (Get-ChildItem -Path $OutputDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host "Package size: $([math]::Round($packageSize, 2)) MB" -ForegroundColor Cyan
Write-Host ""
Write-Host "Contents:" -ForegroundColor Yellow
Write-Host "  python/            - Embedded Python $PythonVersion" -ForegroundColor White
Write-Host "  TradingAgent/      - Your application files" -ForegroundColor White
Write-Host "  RUN_AGENT.bat      - Quick launcher" -ForegroundColor White
Write-Host "  README.md          - User guide" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Test by running: $OutputDir\RUN_AGENT.bat" -ForegroundColor White
Write-Host "2. Zip the '$OutputDir' folder for distribution" -ForegroundColor White
Write-Host "3. Users just extract and run - no installation!" -ForegroundColor White
Write-Host ""
