@echo off
title FoodRescue Tunnel - https://foodrescueapi.serveo.net
:loop
echo.
echo =====================================================
echo  Tunnel URL: https://foodrescueapi.serveo.net
echo  This is a PERMANENT URL - never changes!
echo =====================================================
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R foodrescueapi:80:localhost:8000 serveo.net
echo.
echo [!] Tunnel dropped. Restarting in 3 seconds...
timeout /t 3 /nobreak >nul
goto loop
