# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for SIKANDER OS — IGRIS
Run: python generate_ico.py  (first time only — generates assets/igris.ico)
Then: pyinstaller igris.spec
Output: dist/IGRIS/IGRIS.exe
"""

import sys
from pathlib import Path

ROOT = Path('.').resolve()

block_cipher = None

# ── Collect all data files ──────────────────────────────────
datas = [
    # Frontend (built dist)
    (str(ROOT / 'frontend' / 'dist'),   'frontend/dist'),

    # Assets (icon, images)
    (str(ROOT / 'assets'),              'assets'),

    # Backend core files
    (str(ROOT / 'backend' / 'app'),     'backend/app'),
    (str(ROOT / 'backend' / 'plugins'), 'backend/plugins'),
    (str(ROOT / 'backend' / 'main.py'), 'backend'),

    # Config / env template
    (str(ROOT / '.env.example'),        '.'),
    (str(ROOT / 'backend' / 'config_igris.json'), 'backend'),
]

# ── Hidden imports ───────────────────────────────────────────
hiddenimports = [
    # PyWebView
    'webview',
    'webview.platforms.winforms',
    'webview.platforms.cef',
    'webview.platforms.mshtml',
    # Web Framework
    'fastapi',
    'uvicorn',
    'uvicorn.config',
    'uvicorn.main',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan.on',
    'starlette',
    'pydantic',
    # Security
    'jwt',
    'bcrypt',
    'cryptography',
    'pyotp',
    # System
    'psutil',
    'dotenv',
    # AI
    'openai',
    'anthropic',
    # Finance
    'ccxt',
    # Vector DB
    'chromadb',
    # Speech
    'speech_recognition',
    # Automation
    'pyautogui',
    'keyboard',
    # Utils
    'httpx',
    'aiofiles',
    'rich',
    # Core stdlib
    'threading',
    'subprocess',
    'pathlib',
    'logging',
    'json',
    'os',
    'sys',
    'time',
    'datetime',
    'uuid',
    'asyncio',
    'sqlite3',
]

a = Analysis(
    ['main.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'pandas',
        'scipy', 'cv2', 'torch', 'tensorflow',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='IGRIS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,              # No console window (production)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'assets' / 'igris.ico'),
    version=str(ROOT / 'version_info.txt'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='IGRIS',
)
