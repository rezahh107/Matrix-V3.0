@echo off
setlocal
title Matrix3 Launcher

cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 goto no_uv

echo [Matrix3] Preparing the locked environment...
uv sync --locked
if errorlevel 1 goto failed

echo [Matrix3] Starting the GUI...
uv run --locked python run_gui.py
if errorlevel 1 goto failed

exit /b 0

:no_uv
echo.
echo [Matrix3] ERROR: uv was not found in PATH.
echo Install uv, reopen Windows, then double-click this launcher again.
echo.
pause
exit /b 1

:failed
echo.
echo [Matrix3] ERROR: startup failed. Review the messages above.
echo.
pause
exit /b 1
