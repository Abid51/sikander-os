@echo off
echo ============================================================
echo   IGRIS OS — BACKEND STARTUP
echo ============================================================

cd /d "%~dp0"

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo [SETUP] Creating virtual environment...
    python -m venv venv
)

echo [SETUP] Activating virtual environment...
call venv\Scripts\activate.bat

echo [SETUP] Installing dependencies...
pip install -r requirements.txt --quiet

echo.
echo [IGRIS] Starting backend server on http://127.0.0.1:8000
echo [IGRIS] API docs at   http://127.0.0.1:8000/docs
echo [IGRIS] Press Ctrl+C to stop
echo.
SET PYTHONIOENCODING=utf-8
SET PYTHONUTF8=1
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
