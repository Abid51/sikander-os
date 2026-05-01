"""
SIKANDER OS — IGRIS Desktop Application
Main launcher using PyWebView for native desktop experience.
Provides full dashboard + floating Siri-like orb window.
"""

import sys
import os
import time
import threading
import subprocess
import logging
import urllib.request
from pathlib import Path

# ── SETUP PATHS ─────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    # PyInstaller bundle
    BASE_DIR    = Path(sys._MEIPASS)
    CWD         = Path(os.path.dirname(sys.executable))
else:
    BASE_DIR    = Path(__file__).parent
    CWD         = BASE_DIR

FRONTEND_DIR = BASE_DIR / 'frontend' / 'public'
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = BASE_DIR / 'frontend' / 'dist'
BACKEND_DIR  = BASE_DIR / 'backend'
ASSETS_DIR   = BASE_DIR / 'assets'

LOG_FILE = CWD / 'igris.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger('IGRIS')

# ── DEPENDENCIES CHECK ───────────────────────────────────────
def check_deps():
    missing = []
    for pkg in ['webview']:
        try: __import__(pkg)
        except ImportError: missing.append(pkg)
    if missing:
        log.warning(f"Missing packages: {missing}. Run: pip install {' '.join(missing)}")
    return len(missing) == 0

try:
    import webview
    WEBVIEW_OK = True
except ImportError:
    WEBVIEW_OK = False
    log.error("pywebview not installed. Run: pip install pywebview")


# ── BACKEND PROCESS ──────────────────────────────────────────
_backend_proc = None

def start_backend():
    global _backend_proc
    try:
        backend_main = BACKEND_DIR / 'main.py'
        if not backend_main.exists():
            backend_main = BACKEND_DIR / 'app' / 'main.py'
        if not backend_main.exists():
            log.warning("Backend main.py not found — running without API")
            return

        _backend_proc = subprocess.Popen(
            [sys.executable, str(backend_main)],
            cwd=str(BACKEND_DIR),
            # Avoid pipe backpressure deadlocks; backend logs directly.
            stdout=None,
            stderr=None,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        log.info(f"Backend started — PID {_backend_proc.pid}")
        # Wait briefly for backend health endpoint so frontend actions
        # don't race against API startup.
        health_url = "http://127.0.0.1:8000/health"
        deadline = time.time() + 30
        while time.time() < deadline:
            if _backend_proc.poll() is not None:
                log.error(f"Backend exited early with code {_backend_proc.returncode}")
                return
            try:
                with urllib.request.urlopen(health_url, timeout=1) as res:
                    if res.status == 200:
                        log.info("Backend health check passed.")
                        return
            except Exception:
                time.sleep(0.3)
        log.warning("Backend health check timeout; continuing startup.")
    except Exception as e:
        log.error(f"Backend failed to start: {e}")

def stop_backend():
    global _backend_proc
    if _backend_proc:
        try:
            _backend_proc.terminate()
            _backend_proc.wait(timeout=5)
            log.info("Backend stopped.")
        except Exception as e:
            log.error(f"Error stopping backend: {e}")


# ── PYWEBVIEW API ────────────────────────────────────────────
class IgrisAPI:
    """
    JavaScript ↔ Python bridge.
    Call these from JS via: window.pywebview.api.method_name()
    """

    def __init__(self):
        self._dashboard_window = None
        self._orb_window       = None

    def set_windows(self, dash_win, orb_win):
        self._dashboard_window = dash_win
        self._orb_window       = orb_win

    # ── Dashboard ──
    def show_dashboard(self):
        """Bring the full dashboard to front."""
        if self._dashboard_window:
            self._dashboard_window.show()
            self._dashboard_window.restore()

    def hide_dashboard(self):
        if self._dashboard_window:
            self._dashboard_window.hide()

    # ── Orb ──
    def show_orb(self):
        """Show the floating Siri-like orb window."""
        if self._orb_window:
            self._orb_window.show()
            self._orb_window.restore()

    def hide_orb(self):
        if self._orb_window:
            self._orb_window.hide()

    def close_orb(self):
        if self._orb_window:
            self._orb_window.hide()

    # ── System query ──
    def get_system_info(self):
        """Return basic system info to display in the HUD."""
        try:
            import psutil
            return {
                'cpu':    psutil.cpu_percent(interval=0.3),
                'memory': psutil.virtual_memory().percent,
                'disk':   psutil.disk_usage('/').percent,
            }
        except ImportError:
            return {'cpu': 0, 'memory': 0, 'disk': 0}

    def quit(self):
        """Full application quit."""
        stop_backend()
        webview.windows[0].destroy() if webview.windows else None

    # ── Hotkey helper ──
    def open_orb_from_hotkey(self):
        self.show_orb()
        if self._orb_window:
            self._orb_window.evaluate_js("vibrate();")


# ── HOTKEY LISTENER (Ctrl+Space = summon orb) ────────────────
def start_hotkey_listener(api: IgrisAPI):
    try:
        import keyboard
        def on_hotkey():
            log.info("Global hotkey triggered — showing orb")
            api.open_orb_from_hotkey()
        keyboard.add_hotkey('ctrl+space', on_hotkey)
        log.info("Global hotkey: Ctrl+Space → IGRIS Orb")
        keyboard.wait()  # blocks thread
    except ImportError:
        log.warning("keyboard package not installed — no global hotkey. Run: pip install keyboard")
    except Exception as e:
        log.error(f"Hotkey listener error: {e}")


# ── ICON PATH ────────────────────────────────────────────────
def get_icon():
    for name in ['igris.ico', 'igris.png', 'icon.ico']:
        p = ASSETS_DIR / name
        if p.exists(): return str(p)
    return None


# ── MAIN ─────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("  SIKANDER OS — IGRIS  v2.0")
    log.info("  Starting application…")
    log.info("=" * 60)

    if not WEBVIEW_OK:
        print("\n[ERROR] pywebview not installed.")
        print("Run: pip install pywebview\n")
        input("Press Enter to exit…")
        sys.exit(1)

    # Start backend in background
    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()

    api = IgrisAPI()
    icon = get_icon()

    # ── DASHBOARD WINDOW ──────────────────────────────────
    dash_file = FRONTEND_DIR / 'quantum-hud.html'
    if not dash_file.exists():
        dash_file = FRONTEND_DIR / 'index.html'
    dash_url = dash_file.as_uri()
    log.info(f"Dashboard: {dash_url}")

    dash_win = webview.create_window(
        title            = 'SIKANDER OS — IGRIS',
        url              = dash_url,
        js_api           = api,
        width            = 1920,
        height           = 1080,
        resizable        = True,
        fullscreen       = False,
        shadow           = True,
        frameless        = False,
        easy_drag        = False,
        background_color = '#000000',
        min_size         = (900, 600),
    )
    # ── ORB WINDOW (Siri-like) ────────────────────────────
    orb_file = FRONTEND_DIR / 'igris-orb.html'
    if not orb_file.exists():
        orb_file = FRONTEND_DIR / 'index.html'
    orb_url = orb_file.as_uri()
    log.info(f"Orb window: {orb_url}")

    orb_win = webview.create_window(
        title            = 'IGRIS',
        url              = orb_url,
        js_api           = api,
        width            = 320,
        height           = 440,
        resizable        = False,
        frameless        = True,
        easy_drag        = True,
        shadow           = True,
        on_top           = True,
        background_color = '#000000',     # pywebview expects a hex triplet (RRGGBB)
        hidden           = True,          # hidden by default
    )

    api.set_windows(dash_win, orb_win)

    # ── HOTKEY THREAD ─────────────────────────────────────
    hk_thread = threading.Thread(
        target=start_hotkey_listener,
        args=(api,),
        daemon=True
    )
    hk_thread.start()

    # ── START WEBVIEW ─────────────────────────────────────
    log.info("Launching webview over local HTTP server…")
    webview.start(
        debug     = '--debug' in sys.argv,
        icon      = icon,
        private_mode = False,
        http_server = True, # Use internal HTTP server instead of file://
    )

    # Cleanup on exit
    stop_backend()
    log.info("IGRIS shutdown complete.")


if __name__ == '__main__':
    main()
