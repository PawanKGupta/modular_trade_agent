# Build All-in-One Installer for Modular Trade Agent
# This creates a single .exe that includes Python, dependencies, and project files

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Building All-in-One Installer" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$OutputDir = "installer_build"
$InstallerExe = "ModularTradeAgent_Setup.exe"

# Step 1: Clean previous builds
Write-Host "[1/6] Cleaning previous builds..." -ForegroundColor Green
if (Test-Path $OutputDir) {
    Remove-Item -Recurse -Force $OutputDir
}
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
}
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}

# Step 2: Create portable package first
Write-Host "[2/6] Creating portable package..." -ForegroundColor Green
.\create_portable_package.ps1
if (-Not (Test-Path "portable_package")) {
    Write-Host "ERROR: Portable package creation failed!" -ForegroundColor Red
    exit 1
}

# Step 3: Download NSSM (for service installation)
Write-Host "[3/6] Downloading NSSM..." -ForegroundColor Green
$nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
$nssmZip = "$OutputDir\nssm.zip"
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

try {
    Invoke-WebRequest -Uri $nssmUrl -OutFile $nssmZip
    Expand-Archive -Path $nssmZip -DestinationPath "$OutputDir\nssm_temp" -Force
    
    # Copy 64-bit nssm.exe to installer directory
    Copy-Item "$OutputDir\nssm_temp\nssm-2.24\win64\nssm.exe" "installer\nssm.exe" -Force
    
    Remove-Item -Recurse -Force "$OutputDir\nssm_temp"
    Remove-Item $nssmZip
    
    Write-Host "  ✓ NSSM downloaded" -ForegroundColor White
} catch {
    Write-Host "  ! NSSM download failed (optional)" -ForegroundColor Yellow
}

# Step 4: Create PyInstaller spec for the installer
Write-Host "[4/6] Creating installer spec..." -ForegroundColor Green

$specContent = @"
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['installer/setup.py'],
    pathex=[],
    binaries=[
        ('installer/nssm.exe', '.') if os.path.exists('installer/nssm.exe') else None,
    ],
    datas=[
        ('portable_package', 'portable_package'),  # Include entire portable package
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out None binaries
a.binaries = [b for b in a.binaries if b is not None]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='$InstallerExe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Don't compress for faster extraction
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon if available
)
"@

$specContent | Out-File -FilePath "installer_build.spec" -Encoding UTF8

# Step 5: Build installer exe
Write-Host "[5/6] Building installer executable..." -ForegroundColor Green
Write-Host "  This will take 5-10 minutes..." -ForegroundColor Yellow
Write-Host ""

& .\venv\Scripts\pyinstaller.exe installer_build.spec --clean

# Step 6: Verify and summarize
Write-Host ""
Write-Host "[6/6] Verifying build..." -ForegroundColor Green

if (Test-Path "dist\$InstallerExe") {
    $fileSize = (Get-Item "dist\$InstallerExe").Length / 1MB
    
    Write-Host ""
    Write-Host "=====================================" -ForegroundColor Green
    Write-Host "BUILD SUCCESSFUL!" -ForegroundColor Green
    Write-Host "=====================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Installer: dist\$InstallerExe" -ForegroundColor Cyan
    Write-Host "Size: $([math]::Round($fileSize, 2)) MB" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "What's included:" -ForegroundColor Yellow
    Write-Host "  ✓ Python 3.11 embedded" -ForegroundColor White
    Write-Host "  ✓ All Python dependencies" -ForegroundColor White
    Write-Host "  ✓ Complete Trading Agent source" -ForegroundColor White
    Write-Host "  ✓ NSSM for Windows service" -ForegroundColor White
    Write-Host "  ✓ Automated setup wizard" -ForegroundColor White
    Write-Host ""
    Write-Host "User Experience:" -ForegroundColor Yellow
    Write-Host "  1. Run $InstallerExe" -ForegroundColor White
    Write-Host "  2. Enter credentials in GUI" -ForegroundColor White
    Write-Host "  3. Click 'Install' button" -ForegroundColor White
    Write-Host "  4. Done! Service installed & configured" -ForegroundColor White
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Yellow
    Write-Host "  1. Test the installer on a clean Windows VM" -ForegroundColor White
    Write-Host "  2. Distribute dist\$InstallerExe" -ForegroundColor White
    Write-Host "  3. Users run it - no Python installation needed!" -ForegroundColor White
    Write-Host ""
    
} else {
    Write-Host ""
    Write-Host "=====================================" -ForegroundColor Red
    Write-Host "BUILD FAILED!" -ForegroundColor Red
    Write-Host "=====================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check the output above for errors." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
