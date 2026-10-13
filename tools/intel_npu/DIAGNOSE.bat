@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0collect_windows.ps1" %*
set "DIAG_EXIT=%ERRORLEVEL%"
echo.
echo Diagnostic finished. Reports are inside the reports folder beside this file.
pause
exit /b %DIAG_EXIT%
