@echo off
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
  echo Python is missing. Install Python 3.10 or newer and enable Add Python to PATH.
  pause
  exit /b 1
)
if not exist .venv (
  python -m venv .venv
  if errorlevel 1 exit /b 1
)
call .venv\Scripts\activate
if errorlevel 1 exit /b 1
python -m pip install -q -U -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. Check your connection and Python version.
  pause
  exit /b 1
)
python app.py --open-browser
if errorlevel 1 (
  echo.
  echo The downloader could not start. If it says port 5000 is already in use,
  echo close the older downloader terminal with Ctrl+C and run this file again.
)
pause
