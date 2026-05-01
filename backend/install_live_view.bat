# ═══════════════════════════════════════════════════════════════
# Igris Frontend Engine + Live View - Install & Start Script
# Run this file from the backend folder:
#   cd sikander-os\backend
#   .\install_live_view.bat
# ═══════════════════════════════════════════════════════════════
@echo off
echo [Igris] Installing Live View dependencies...
call venv\Scripts\pip.exe install mss --quiet
echo [Igris] mss installed.
echo.
echo [Igris] Starting backend...
call venv\Scripts\python.exe main.py
