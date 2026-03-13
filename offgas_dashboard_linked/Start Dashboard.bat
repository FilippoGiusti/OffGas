@echo off
setlocal
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is not installed or not available in PATH.
  echo Install Node.js first, then run this file again.
  pause
  exit /b 1
)

if not exist node_modules (
  echo Installing dashboard dependencies...
  call npm install
  if errorlevel 1 (
    echo.
    echo Dependency installation failed.
    pause
    exit /b 1
  )
)

start "OffGas Dashboard" cmd /k "cd /d "%~dp0" && npm run dev"
timeout /t 4 /nobreak >nul
start "" "http://localhost:3000"
