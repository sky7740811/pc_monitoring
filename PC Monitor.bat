@echo off
title PC Monitor
cd /d "%~dp0"

:: Auto-elevate to admin (UAC prompt)
>nul 2>&1 net session || (
    powershell -Command "Start-Process '%~dp0PC Monitor.bat' -Verb RunAs"
    exit /b
)

echo [PC Monitor] Verifying dependencies...
pip install psutil fastapi uvicorn websockets pywebview pillow -q
echo [PC Monitor] Starting...
start /B python run.py
exit
