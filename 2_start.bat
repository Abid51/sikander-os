@echo off
echo =======================================================
echo  STARTING SIKANDER SUPREME AI DESKTOP (Knight Commander Igris)
echo =======================================================
echo.

:: 1. Start the Local AI Brain (Ollama)
echo [1/3] Starting Local AI Core (Ollama)...
start "" /B ollama serve >nul 2>&1
timeout /t 3 /nobreak >nul

:: 2. Start the Backend API (FastAPI)
echo [2/3] Starting Central Nervous System (Backend)...
SET PYTHONIOENCODING=utf-8
SET PYTHONUTF8=1
cd backend
if not exist ..\.venv (
    echo [ERROR] Virtual environment '.venv' not found. Please run install.bat first!
    pause
    exit /b 1
)
call ..\.venv\Scripts\activate
start "" /B ..\.venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000 --reload >nul 2>&1
cd ..

timeout /t 2 /nobreak >nul

:: 3. Start the Frontend 3D UI (React + Vite + Electron)
echo [3/3] Starting Futuristic 3D Desktop App...
cd frontend
start "" /B npm run electron:dev >nul 2>&1
cd ..

echo.
echo SYSTEM IS ONLINE!
echo -------------------------------------------------------
echo The Sikander Supreme AI window should now be open.
echo Backend (AI API): http://localhost:8000/docs
echo -------------------------------------------------------
echo Press Ctrl+C to Shutdown.

:: Keep window open
pause
