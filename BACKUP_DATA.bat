@echo off
REM ============================================================
REM Modular Trade Agent - Data Backup Script
REM ============================================================

echo.
echo ============================================================
echo MODULAR TRADE AGENT - DATA BACKUP
echo ============================================================
echo.

REM Get current timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%

REM Create backup directory
set BACKUP_DIR=data_backups\%TIMESTAMP%
echo Creating backup directory: %BACKUP_DIR%
mkdir "%BACKUP_DIR%" 2>nul

REM Backup all JSON files from data directory
echo.
echo Backing up data files...
if exist "data\*.json" (
    copy "data\*.json" "%BACKUP_DIR%\" >nul 2>&1
    if %errorlevel% equ 0 (
        echo   [32m✓[0m JSON files backed up successfully
    ) else (
        echo   [31m✗[0m Failed to backup JSON files
        goto :error
    )
) else (
    echo   [33m⚠[0m No JSON files found in data directory
)

REM Backup CSV files if they exist
if exist "data\*.csv" (
    copy "data\*.csv" "%BACKUP_DIR%\" >nul 2>&1
    echo   [32m✓[0m CSV files backed up
)

REM Backup config files if they exist
if exist "config\*.json" (
    copy "config\*.json" "%BACKUP_DIR%\" >nul 2>&1
    echo   [32m✓[0m Config files backed up
)

REM Display backup summary
echo.
echo ============================================================
echo BACKUP SUMMARY
echo ============================================================
echo Backup Location: %BACKUP_DIR%
echo.
echo Files backed up:
dir /b "%BACKUP_DIR%"
echo.

REM Count files
for /f %%A in ('dir /b "%BACKUP_DIR%" 2^>nul ^| find /c /v ""') do set FILE_COUNT=%%A
echo Total files: %FILE_COUNT%

echo.
echo ============================================================
echo [32m✓ BACKUP COMPLETED SUCCESSFULLY[0m
echo ============================================================
echo.
echo Backup saved to: %CD%\%BACKUP_DIR%
echo.
pause
exit /b 0

:error
echo.
echo ============================================================
echo [31m✗ BACKUP FAILED[0m
echo ============================================================
echo.
pause
exit /b 1
