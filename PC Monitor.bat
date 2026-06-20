@echo off
title PC Monitor
cd /d "%~dp0"

:: Auto-elevate to admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell Start-Process -Verb RunAs -FilePath "%~f0"
    exit /b
)

echo [PC Monitor] Installing...
pip install psutil fastapi uvicorn websockets pywebview pillow -q
python run.py
pause
