@echo off
title Igris OS - Environment Setup
color 0A

echo.
echo  ██╗ ██████╗ ██████╗ ██╗███████╗
echo  ██║██╔════╝ ██╔══██╗██║██╔════╝
echo  ██║██║  ███╗██████╔╝██║███████╗
echo  ██║██║   ██║██╔══██╗██║╚════██║
echo  ██║╚██████╔╝██║  ██║██║███████║
echo  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝╚══════╝
echo.
echo  Sikander OS - Backend Environment Setup
echo ==========================================
echo.

:: ── Step 1: Check Python ────────────────────────────────────────────────────
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please install Python 3.11+ from python.org
    pause
    exit /b 1
)
python --version
echo [OK] Python found.
echo.

:: ── Step 2: Remove old broken venv ───────────────────────────────────────────
echo [2/5] Removing old Linux-based venv (if exists)...
if exist venv (
    rmdir /s /q venv
    echo [OK] Old venv removed.
) else (
    echo [OK] No old venv found.
)
echo.

:: ── Step 3: Create new Windows venv ─────────────────────────────────────────
echo [3/5] Creating new Windows virtual environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create venv!
    pause
    exit /b 1
)
echo [OK] Virtual environment created successfully.
echo.

:: ── Step 4: Upgrade pip ──────────────────────────────────────────────────────
echo [4/5] Upgrading pip...
call venv\Scripts\python.exe -m pip install --upgrade pip --quiet
echo [OK] pip upgraded.
echo.

:: ── Step 5: Install all requirements ────────────────────────────────────────
echo [5/5] Installing all requirements (this may take a few minutes)...
echo.
call venv\Scripts\pip.exe install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Some packages may have failed. Trying core packages only...
    call venv\Scripts\pip.exe install fastapi uvicorn pydantic python-dotenv websockets aiohttp requests psutil pillow mss pygetwindow
)
echo.
echo [OK] Installation complete!
echo.

:: ── Done ─────────────────────────────────────────────────────────────────────
echo ==========================================
echo  ENVIRONMENT READY!
echo  Now run: start_backend.bat
echo ==========================================
echo.
pause
