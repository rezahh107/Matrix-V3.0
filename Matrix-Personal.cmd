@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>&1
if errorlevel 1 (
  echo [Matrix] uv not found in PATH.
  exit /b 1
)
uv run --no-project --python 3.11 python -m tools.personal_release %*
exit /b %errorlevel%
