@echo off
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr ESTABLISHED') do taskkill /PID %%a /F >nul 2>nul
echo Dashboard stop command sent.
pause
