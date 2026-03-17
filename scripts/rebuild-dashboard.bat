@echo off
cd /d "%~dp0..\offgas_dashboard_linked"
call npm install
call npm run build
