# Quick Start Script for Docker Setup (PowerShell)
# This script helps you get started with Docker quickly on Windows
# Run from project root: .\docker\docker-quickstart.ps1

# Get script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$DockerDir = $ScriptDir

Write-Host "Docker Quick Start for Trading Agent" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project root: $ProjectRoot" -ForegroundColor Gray
Write-Host "Docker dir: $DockerDir" -ForegroundColor Gray
Write-Host ""

# Check if Docker is installed
try {
    $dockerVersion = docker --version
    Write-Host "Docker is installed: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "Docker is not installed!" -ForegroundColor Red
    Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# Check if Docker is running
try {
    docker info | Out-Null
    Write-Host "Docker is running" -ForegroundColor Green
} catch {
    Write-Host "Docker is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Check for .env file in project root
Set-Location $ProjectRoot
if (-not (Test-Path .env)) {
    Write-Host ".env file not found in project root" -ForegroundColor Yellow
    Write-Host "Creating .env from template..." -ForegroundColor Yellow

    @"
# Database
DB_URL=sqlite:///./data/app.db

# Timezone
TZ=Asia/Kolkata

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Admin User Auto-Creation (only on first deployment when database is empty)
# The API server will automatically create an admin user on startup if:
# 1. Database has zero users
# 2. ADMIN_EMAIL and ADMIN_PASSWORD are set below
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeThisPassword123!
ADMIN_NAME=Admin User
"@ | Out-File -FilePath .env -Encoding utf8

    Write-Host "Created .env file (please edit with your settings)" -ForegroundColor Green
} else {
    Write-Host ".env file exists" -ForegroundColor Green
}

# Note: Credentials are now stored in database via web UI
Write-Host " Credentials are stored in database via web UI" -ForegroundColor Cyan
Write-Host "   Configure them after starting services at http://localhost:5173" -ForegroundColor Gray
Write-Host ""
Write-Host " Admin user will be auto-created on first startup (if DB is empty)" -ForegroundColor Cyan
Write-Host "   Check .env file for ADMIN_EMAIL and ADMIN_PASSWORD" -ForegroundColor Gray

Write-Host ""
Write-Host "Building Docker images..." -ForegroundColor Cyan
Write-Host "This may take 5-10 minutes on first run..." -ForegroundColor Yellow
Set-Location $DockerDir
docker-compose -f docker-compose.yml build

Write-Host ""
Write-Host "Starting services..." -ForegroundColor Cyan
docker-compose -f docker-compose.yml up -d

Write-Host ""
Write-Host "Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "Service Status:" -ForegroundColor Cyan
docker-compose -f docker-compose.yml ps

Write-Host ""
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Access your services:" -ForegroundColor Cyan
Write-Host "  - Web Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  - API Server:  http://localhost:8000" -ForegroundColor White
Write-Host "  - Health Check: http://localhost:8000/health" -ForegroundColor White
Write-Host ""
Write-Host "Useful commands (run from docker/ folder):" -ForegroundColor Cyan
Write-Host "  View logs:        docker-compose -f docker-compose.yml logs -f" -ForegroundColor Gray
Write-Host "  Stop services:    docker-compose -f docker-compose.yml down" -ForegroundColor Gray
Write-Host "  Restart service:  docker-compose -f docker-compose.yml restart <service-name>" -ForegroundColor Gray
Write-Host "  View status:      docker-compose -f docker-compose.yml ps" -ForegroundColor Gray
Write-Host ""
Write-Host "For more help, see docker/README.md" -ForegroundColor Cyan
