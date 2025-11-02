@echo off
REM ============================================================
REM Modular Trade Agent - Uninstallation Script
REM ============================================================

echo.
echo ============================================================
echo MODULAR TRADE AGENT - UNINSTALLATION
echo ============================================================
echo.

REM Check for admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [31mERROR: Administrator rights required![0m
    echo Please run this script as Administrator.
    echo.
    pause
    exit /b 1
)

echo [33mWARNING: This will remove all Modular Trade Agent services and files![0m
echo.
set /p CONFIRM="Are you sure you want to uninstall? (yes/no): "
if /i not "%CONFIRM%"=="yes" (
    echo.
    echo Uninstallation cancelled.
    pause
    exit /b 0
)

echo.
echo ============================================================
echo STOPPING AND REMOVING SERVICES
echo ============================================================
echo.

REM Define services to remove
set SERVICES=ModularTradeAgent_Main ModularTradeAgent_Monitor ModularTradeAgent_EOD ModularTradeAgent_Sell

REM Stop and remove each service
for %%S in (%SERVICES%) do (
    echo Checking service: %%S
    sc query %%S >nul 2>&1
    if %errorlevel% equ 0 (
        echo   Stopping %%S...
        net stop %%S >nul 2>&1
        timeout /t 2 /nobreak >nul
        
        echo   Removing %%S...
        sc delete %%S >nul 2>&1
        if %errorlevel% equ 0 (
            echo   [32m✓[0m Service %%S removed
        ) else (
            echo   [31m✗[0m Failed to remove service %%S
        )
    ) else (
        echo   [33m⚠[0m Service %%S not found
    )
    echo.
)

echo ============================================================
echo BACKING UP DATA FILES
echo ============================================================
echo.

set INSTALL_DIR=C:\ProgramData\ModularTradeAgent

if exist "%INSTALL_DIR%\data" (
    REM Create backup before deletion
    for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
    set TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%
    set BACKUP_DIR=C:\ProgramData\ModularTradeAgent_Backup_%TIMESTAMP%
    
    echo Creating backup at: %BACKUP_DIR%
    mkdir "%BACKUP_DIR%" 2>nul
    
    xcopy /E /I /Y "%INSTALL_DIR%\data" "%BACKUP_DIR%\data" >nul 2>&1
    xcopy /E /I /Y "%INSTALL_DIR%\logs" "%BACKUP_DIR%\logs" >nul 2>&1
    copy "%INSTALL_DIR%\kotak_neo.env" "%BACKUP_DIR%\" >nul 2>&1
    
    if %errorlevel% equ 0 (
        echo   [32m✓[0m Data backed up to: %BACKUP_DIR%
    ) else (
        echo   [33m⚠[0m Backup completed with warnings
    )
) else (
    echo   [33m⚠[0m No data directory found
)

echo.
echo ============================================================
echo REMOVING INSTALLATION DIRECTORY
echo ============================================================
echo.

if exist "%INSTALL_DIR%" (
    echo Removing: %INSTALL_DIR%
    rmdir /S /Q "%INSTALL_DIR%" 2>nul
    
    if exist "%INSTALL_DIR%" (
        echo   [31m✗[0m Failed to remove installation directory
        echo   Some files may be in use. Please close all applications and try again.
    ) else (
        echo   [32m✓[0m Installation directory removed
    )
) else (
    echo   [33m⚠[0m Installation directory not found
)

echo.
echo ============================================================
echo REMOVING DESKTOP SHORTCUT
echo ============================================================
echo.

set SHORTCUT=%USERPROFILE%\Desktop\Trading Agent.lnk
if exist "%SHORTCUT%" (
    del "%SHORTCUT%" >nul 2>&1
    if %errorlevel% equ 0 (
        echo   [32m✓[0m Desktop shortcut removed
    ) else (
        echo   [31m✗[0m Failed to remove desktop shortcut
    )
) else (
    echo   [33m⚠[0m Desktop shortcut not found
)

echo.
echo ============================================================
echo CLEANING UP ENVIRONMENT VARIABLES (OPTIONAL)
echo ============================================================
echo.
echo If you set user environment variables, you may want to remove them:
echo   - TELEGRAM_BOT_TOKEN
echo   - TELEGRAM_CHAT_ID
echo.
set /p CLEAN_ENV="Remove environment variables? (yes/no): "
if /i "%CLEAN_ENV%"=="yes" (
    reg delete "HKCU\Environment" /v TELEGRAM_BOT_TOKEN /f >nul 2>&1
    reg delete "HKCU\Environment" /v TELEGRAM_CHAT_ID /f >nul 2>&1
    echo   [32m✓[0m Environment variables removed
)

echo.
echo ============================================================
echo UNINSTALLATION SUMMARY
echo ============================================================
echo.

REM Check if uninstallation was successful
set UNINSTALL_SUCCESS=1

REM Check services
for %%S in (%SERVICES%) do (
    sc query %%S >nul 2>&1
    if %errorlevel% equ 0 (
        set UNINSTALL_SUCCESS=0
    )
)

REM Check installation directory
if exist "%INSTALL_DIR%" (
    set UNINSTALL_SUCCESS=0
)

if %UNINSTALL_SUCCESS% equ 1 (
    echo [32m✓ UNINSTALLATION COMPLETED SUCCESSFULLY[0m
    echo.
    echo All components have been removed.
    if exist "%BACKUP_DIR%" (
        echo.
        echo Your data has been backed up to:
        echo %BACKUP_DIR%
    )
) else (
    echo [31m✗ UNINSTALLATION INCOMPLETE[0m
    echo.
    echo Some components could not be removed.
    echo Please check the messages above and try again.
)

echo.
echo ============================================================
echo.
pause
