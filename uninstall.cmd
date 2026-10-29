@echo off
set "SOLARHUB_ARGS="
:loop
if "%~1"=="" goto run
if /I "%~1"=="--keep-data" set "SOLARHUB_ARGS=%SOLARHUB_ARGS% -KeepData"
if /I "%~1"=="--yes" set "SOLARHUB_ARGS=%SOLARHUB_ARGS% -Yes"
if /I "%~1"=="-y" set "SOLARHUB_ARGS=%SOLARHUB_ARGS% -Yes"
shift
goto loop
:run
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %SOLARHUB_ARGS%
pause
