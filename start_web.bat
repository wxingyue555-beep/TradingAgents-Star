@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo   ============================================
echo     TradingAgents Web Server (Windows)
echo   ============================================
echo.

set PORT=8000
if not "%1"=="" set PORT=%1

:: check venv
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found, please deploy first
    pause
    exit /b 1
)

:: check deps
.venv\Scripts\python -c "import fastapi, uvicorn, tradingagents" >nul 2>&1
if errorlevel 1 (
    echo [INSTALL] Installing web dependencies...
    .venv\Scripts\python -m pip install fastapi uvicorn jinja2 -q
)

:: kill process on target port
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    echo [CLEAN] Killing PID %%a on port %PORT%
    taskkill /f /pid %%a >nul 2>&1
)

:: launch
echo [START] http://localhost:%PORT%
echo [TIP] Press Ctrl+C to stop
echo.

.venv\Scripts\python -m uvicorn web_app.main:app --host 0.0.0.0 --port %PORT% --reload --log-level info

pause
