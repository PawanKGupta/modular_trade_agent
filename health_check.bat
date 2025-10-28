@echo off
REM Health Check Wrapper for Modular Trade Agent
REM Runs comprehensive health check and displays results

echo =====================================
echo Modular Trade Agent - Health Check
echo =====================================
echo.

REM Check if py launcher is available (preferred for Windows)
py --version >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    REM Run health check with py launcher
    py health_check.py
    goto :end
)

REM Fallback to python command
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python health_check.py
    goto :end
)

REM Check if installed via installer
if exist "C:\ProgramData\ModularTradeAgent\python\python.exe" (
    C:\ProgramData\ModularTradeAgent\python\python.exe health_check.py
    goto :end
)

REM No Python found
echo ERROR: Python not found
echo.
echo Please install Python from python.org or the Microsoft Store
echo Or run from the installation directory if using the installer.
pause
exit /b 1

:end

echo.
pause
