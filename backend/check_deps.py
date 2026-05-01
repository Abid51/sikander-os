"""Quick dependency check for all Igris Phase 2/3 packages."""
import sys
sys.path.insert(0, '.')

results = []

tests = [
    ("discord.py",    "import discord; v=discord.__version__",             "discord"),
    ("twilio",        "from twilio.rest import Client",                    "twilio"),
    ("redis",         "import redis; v=redis.__version__",                 "redis"),
    ("whisper",       "import whisper",                                    "whisper"),
    ("PyPDF2",        "import PyPDF2; v=PyPDF2.__version__",               "PyPDF2"),
    ("python-docx",   "import docx",                                       "docx"),
    ("pdfplumber",    "import pdfplumber; v=pdfplumber.__version__",       "pdfplumber"),
    ("openpyxl",      "import openpyxl; v=openpyxl.__version__",           "openpyxl"),
    ("sounddevice",   "import sounddevice; v=sounddevice.__version__",     "sounddevice"),
    ("soundfile",     "import soundfile; v=soundfile.__version__",         "soundfile"),
    ("playwright",    "from playwright.sync_api import sync_playwright",   "playwright"),
    ("fastapi",       "import fastapi; v=fastapi.__version__",             "fastapi"),
    ("chromadb",      "import chromadb; v=chromadb.__version__",           "chromadb"),
]

for name, code, _ in tests:
    try:
        exec(code)
        try:
            print(f"[OK]   {name} v{v}")
        except NameError:
            print(f"[OK]   {name}")
        results.append(True)
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        results.append(False)

passed = sum(results)
total = len(results)
print(f"\n=== {passed}/{total} packages ready ===")
