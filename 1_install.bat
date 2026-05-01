@echo off
echo =======================================================
echo  ROCKET SIKANDER SUPREME AI DESKTOP - WINDOWS INSTALLER ROCKET
echo =======================================================
echo.

:: 1. Install Frontend Packages
echo [1/3] Installing Windows Desktop App Packages (React, Electron, Three.js)...
cd frontend
call npm install
echo Frontend packages installed successfully!
echo.
cd ..

:: 2. Install Backend Environment
echo [2/3] Setting up Backend Environment (FastAPI, Computer Vision, Automation)...
cd backend
if not exist venv (
    python -m venv venv
)

echo NOTE: Please download and install Tesseract-OCR manually from:
echo https://github.com/UB-Mannheim/tesseract/wiki
echo It is required for Igris's 'Screen Reading' (Vision) ability.
echo.

call venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel

:: Note: PyAudio is optional. If it fails, voice features will be disabled but the system will run.
echo Installing PyAudio...
pip install pyaudio || echo [WARNING] PyAudio failed to install. Voice input will be disabled.

echo Installing PyTorch and Transformers (This may take a while)...
:: Install CPU version by default. For GPU, change to cu118 or cu121 index URL
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install "fastapi[all]" "uvicorn[standard]" pydantic python-dotenv websockets
pip install "numpy<2.0.0"
pip install "langchain<0.2.0" "langchain-community<0.2.0" "langchain-openai<0.2.0"
pip install crewai psutil pyautogui pytesseract Pillow pyttsx3 requests SpeechRecognition PyGetWindow ccxt feedparser schedule
pip install datasets WMI beautifulsoup4 pyinstaller setuptools wheel
call venv\Scripts\deactivate
echo Backend environment setup successfully!
echo.
cd ..

:: 3. Install Local AI Model (Ollama)
echo [3/3] Installing Local AI Model Engine (Ollama)...
echo Please make sure you have installed Ollama for Windows from https://ollama.com/download/windows
echo If installed, we will now pull the Llama3 model.
echo.

:: Start Ollama in background if not already running (Windows handles this via its own service usually)
:: Just pulling the model directly:
echo Downloading 'llama3' (Local Model for Sikander Brain)...
ollama pull llama3
echo Local AI Model installed successfully!
echo.

echo =======================================================
echo  INSTALLATION COMPLETE! 
echo You can now start Sikander AI by running: start.bat
echo =======================================================
pause
