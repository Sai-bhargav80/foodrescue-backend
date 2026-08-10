@echo off
title FoodRescue Backend Server
:loop
echo ===================================================
echo [!] Starting FoodRescue FastAPI Backend Server...
echo ===================================================
python -m uvicorn main:app --host 0.0.0.0 --port 8000
echo.
echo [!] Backend server stopped. Auto-restarting in 5 seconds...
timeout /t 5
goto loop
