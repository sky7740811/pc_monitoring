@echo off
title PC Monitor
cd /d "%~dp0"
echo [PC Monitor] Verifying dependencies...
pip install psutil fastapi uvicorn websockets pywebview pillow -q
echo [PC Monitor] Starting...
python run.py
pause
