@echo off
REM One-command setup for Windows:  install.bat [--browser]
cd /d "%~dp0"
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" || (echo Python 3.11+ is required. Install it from python.org and re-run. & exit /b 1)
python -m venv .venv || exit /b 1
call .venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
if "%1"=="--browser" (
  python -m pip install --quiet -e ".[browser]" || exit /b 1
  python -m playwright install chromium
) else (
  python -m pip install --quiet -e . || exit /b 1
)
python -m unittest discover -s tests
python -m jobagent import data\inbox\2026-10-03_indeed_bayt.json
python -m jobagent doctor
echo.
echo Installed. Each time you open a terminal:
echo   .venv\Scripts\activate
echo   jobagent list
