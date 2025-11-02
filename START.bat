@echo off
REM Quick start script for Modular Trade Agent
REM This batch file can be used with the executable

echo =====================================
echo Modular Trade Agent
echo =====================================
echo.

REM Check if executable exists
if exist "ModularTradeAgent.exe" (
    echo Starting Modular Trade Agent...
    echo.
    ModularTradeAgent.exe
) else (
    echo ERROR: ModularTradeAgent.exe not found!
    echo.
    echo Please build the executable first using:
echo   .\scripts\build\build.ps1
    echo.
    pause
    exit /b 1
)

echo.
echo Agent stopped.
pause
