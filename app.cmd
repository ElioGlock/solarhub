@echo off
rem Solarhub no Windows: prepara (na primeira vez) e abre o app. Uso: app.cmd  [--install]
set "SOLARHUB_ARGS="
if /I "%~1"=="--install" set "SOLARHUB_ARGS=-Install"
if /I "%~1"=="-i" set "SOLARHUB_ARGS=-Install"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0app.ps1" %SOLARHUB_ARGS%
if errorlevel 1 pause
