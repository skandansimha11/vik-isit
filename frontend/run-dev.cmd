@echo off
set "PATH=C:\Users\DELL\AppData\Local\node-portable\node-v22.14.0-win-x64;%PATH%"
cd /d "%~dp0"
call npm run dev
