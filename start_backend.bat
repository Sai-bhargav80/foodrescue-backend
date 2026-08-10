@echo off
title FoodRescue Backend (Auto-Restart)
:loop
echo.
echo =====================================================
echo  Starting FoodRescue FastAPI Backend on port 8000
echo =====================================================
cd /d "C:\project\FoodRescueBackend"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
echo.
echo [!] Backend stopped. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
