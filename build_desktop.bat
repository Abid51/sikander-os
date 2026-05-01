@echo off
:: ═══════════════════════════════════════════════════════════════════════
::  SIKANDER OS — IGRIS — COMPLETE DESKTOP BUILD SCRIPT
::  Builds frontend → generates ICO → packages desktop exe
::  Output: dist\IGRIS\IGRIS.exe
:: ═══════════════════════════════════════════════════════════════════════

echo.
echo ██████████████████████████████████████████████
echo   SIKANDER OS — IGRIS DESKTOP BUILD
echo ██████████████████████████████████████████████
echo.

:: Step 1: Build Frontend
echo [1/4] Building Frontend (React/TypeScript)...
cd frontend
call npm install --silent
if errorlevel 1 (
    echo ERROR: npm install failed
    pause
    exit /b 1
)
call npm run build
if errorlevel 1 (
    echo ERROR: Frontend build failed
    pause
    exit /b 1
)
cd ..
echo [1/4] Frontend built successfully ✓

:: Step 2: Generate ICO
echo [2/4] Generating Windows icon (igris.ico)...
python generate_ico.py
if errorlevel 1 (
    echo WARNING: ICO generation failed — build will continue without icon
)
echo [2/4] ICO generated ✓

:: Step 3: PyInstaller
echo [3/4] Packaging with PyInstaller...
python -m PyInstaller igris.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller failed
    pause
    exit /b 1
)
echo [3/4] PyInstaller complete ✓

:: Step 4: Result
echo [4/4] Build complete!
echo.
echo ════════════════════════════════════════════
echo   Output: dist\IGRIS\IGRIS.exe
echo ════════════════════════════════════════════
echo.

if exist "dist\IGRIS\IGRIS.exe" (
    echo ✅ IGRIS.exe created successfully!
) else (
    echo ❌ IGRIS.exe not found — check build logs
)

pause
