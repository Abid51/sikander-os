@echo off
echo =======================================================
echo  🚀 SIKANDER AI OS - FULL .EXE BUILD SCRIPT 🚀
echo =======================================================
echo.

:: 1. Compile Backend to EXE
echo [1/3] Compiling Python Backend to Executable...
cd backend
if not exist venv (
    echo [ERROR] Virtual environment 'venv' not found. Please run 1_install.bat first!
    pause
    exit /b 1
)

:: Fix for Python executable not found in venv
set PYTHON_EXE=venv\Scripts\python.exe
if not exist %PYTHON_EXE% (
    set PYTHON_EXE=python
)

call venv\Scripts\activate
%PYTHON_EXE% -m pip install pyinstaller

echo Running PyInstaller...
%PYTHON_EXE% -m PyInstaller --noconfirm --onedir --noconsole --name backend --hidden-import=uvicorn.logging --hidden-import=uvicorn.loops.auto --hidden-import=uvicorn.protocols.http.auto --hidden-import=uvicorn.protocols.websockets.auto --hidden-import=uvicorn.lifespan.on main.py
if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller failed!
    pause
    exit /b %ERRORLEVEL%
)

:: Move the generated folder to frontend root so electron-builder can bundle it
if exist ..\frontend\backend rmdir /S /Q ..\frontend\backend
xcopy /E /I /Y dist\backend ..\frontend\backend\
call venv\Scripts\deactivate
cd ..

:: 2. Build Frontend into final Installer
echo [2/3] Compiling React+Electron to Windows Installer...
cd frontend
call npm install
call npm run electron:build
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Electron Build failed!
    pause
    exit /b %ERRORLEVEL%
)
cd ..

echo.
echo =======================================================
echo 🎉 BUILD COMPLETE! 🎉
echo Your setup file is located in:
echo frontend\release\Sikander AI Setup 1.0.0.exe
echo =======================================================
pause
