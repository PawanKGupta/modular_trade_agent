# Build script for creating Windows executable
# PowerShell script to automate the build process

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Modular Trade Agent - Build Script" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-Not (Test-Path "venv")) {
    Write-Host "ERROR: Virtual environment not found!" -ForegroundColor Red
    Write-Host "Please create a virtual environment first:" -ForegroundColor Yellow
    Write-Host "  python -m venv venv" -ForegroundColor Yellow
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Green
& .\venv\Scripts\Activate.ps1

# Install PyInstaller if not already installed
Write-Host "Checking PyInstaller installation..." -ForegroundColor Green
$pyinstallerInstalled = pip list | Select-String "pyinstaller"
if (-Not $pyinstallerInstalled) {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
}

# Clean previous builds
Write-Host "Cleaning previous builds..." -ForegroundColor Green
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
}
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}

# Build executable using spec file
Write-Host ""
Write-Host "Building executable..." -ForegroundColor Green
Write-Host "This may take several minutes..." -ForegroundColor Yellow
Write-Host ""

pyinstaller build_executable.spec --clean

# Check if build was successful
if (Test-Path "dist\ModularTradeAgent.exe") {
    Write-Host ""
    Write-Host "=====================================" -ForegroundColor Green
    Write-Host "Build successful!" -ForegroundColor Green
    Write-Host "=====================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Executable location: dist\ModularTradeAgent.exe" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "File size: " -NoNewline
    $fileSize = (Get-Item "dist\ModularTradeAgent.exe").Length / 1MB
    Write-Host "$([math]::Round($fileSize, 2)) MB" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Copy the 'dist' folder to your target machine" -ForegroundColor White
    Write-Host "2. Create a kotak_neo.env file with your credentials" -ForegroundColor White
    Write-Host "3. Run ModularTradeAgent.exe" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "=====================================" -ForegroundColor Red
    Write-Host "Build failed!" -ForegroundColor Red
    Write-Host "=====================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check the output above for errors." -ForegroundColor Yellow
    exit 1
}
