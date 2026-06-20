@echo off
title PC Monitor
cd /d "%~dp0"
echo [PC Monitor] Installing...
pip install psutil fastapi uvicorn websockets pywebview pillow -q
python run.py
pause
