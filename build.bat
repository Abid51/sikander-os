@echo off
title IGRIS — Build System
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   SIKANDER OS — IGRIS  Build Script      ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ── Step 1: Install dependencies ──────────────────────────
echo [1/5] Installing Python dependencies...
pip install pywebview pyinstaller keyboard pillow psutil --quiet
pip install fastapi uvicorn python-jose bcrypt cryptography pyotp --quiet
echo  ✓ Dependencies installed

:: ── Step 2: Create assets directory ─────────────────────
echo.
echo [2/5] Setting up assets...
if not exist assets mkdir assets

:: Copy IGRIS image to assets
if exist igris_icon.png copy igris_icon.png assets\igris_icon.png >nul 2>&1

:: ── Step 3: Convert PNG → ICO ─────────────────────────────
echo.
echo [3/5] Creating desktop icon...
python make_icon.py
if errorlevel 1 (
    echo  ⚠ Icon conversion failed — using default
) else (
    echo  ✓ Icon created: assets\igris.ico
)

:: ── Step 4: Create .env if missing ───────────────────────
echo.
echo [4/5] Checking configuration...
if not exist .env (
    echo IGRIS_JWT_SECRET=change-this-secret-key-in-production> .env
    echo IGRIS_ENCRYPTION_KEY=>> .env
    echo OPENAI_API_KEY=>> .env
    echo HOST=127.0.0.1>> .env
    echo PORT=8000>> .env
    echo  ✓ Created .env template — add your API keys!
) else (
    echo  ✓ .env exists
)

:: ── Step 5: PyInstaller build ─────────────────────────────
echo.
echo [5/5] Building IGRIS.exe with PyInstaller...
echo  This may take 2-5 minutes...
echo.
pyinstaller igris.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo  ✗ Build FAILED. Check errors above.
    echo.
) else (
    echo.
    echo  ╔══════════════════════════════════════════╗
    echo  ║   ✓ BUILD SUCCESSFUL!                    ║
    echo  ║                                          ║
    echo  ║   Executable: dist\IGRIS\IGRIS.exe       ║
    echo  ║   Run it to launch IGRIS!                ║
    echo  ╚══════════════════════════════════════════╝
    echo.

    :: Create desktop shortcut
    echo Creating desktop shortcut...
    powershell -Command ^
        "$ws = New-Object -ComObject WScript.Shell; ^
         $sc = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\IGRIS.lnk'); ^
         $sc.TargetPath = '%CD%\dist\IGRIS\IGRIS.exe'; ^
         $sc.WorkingDirectory = '%CD%\dist\IGRIS'; ^
         $sc.IconLocation = '%CD%\assets\igris.ico'; ^
         $sc.Description = 'SIKANDER OS — IGRIS AI Assistant'; ^
         $sc.Save()"
    echo  ✓ Desktop shortcut created: IGRIS.lnk
)

echo.
pause
