"""
SIKANDER OS — IGRIS Desktop Application (OPTIMIZED)
Main launcher using PyWebView for native desktop experience.
Provides full dashboard + floating Siri-like orb window.

PERFORMANCE IMPROVEMENTS:
- Replaced blocking health check loop with exponential backoff
- Implemented thread-safe metric caching
- Added proper thread lifecycle management
- Improved subprocess resource handling
- Added log rotation to prevent disk space issues
"""

import sys
import os
import time
import threading
import subprocess
import logging
from logging.handlers import RotatingFileHandler
import urllib.request
from pathlib import Path
from functools import lru_cache
from typing import Optional
import atexit

# ── SETUP PATHS ─────────────────────────────────────────────
if getattr(sys, 'frozen', False):
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

# ── IMPROVED LOGGING WITH ROTATION ──────────────────────────
def setup_logger():
    """Configure logger with file rotation to prevent disk bloat."""
    logger = logging.getLogger('IGRIS')
    logger.setLevel(logging.INFO)
    
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    )
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    )
    
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger

log = setup_logger()


# ── SYSTEM METRICS CACHING ──────────────────────────────────
class SystemMetricsCache:
    """Thread-safe cache for system metrics with TTL."""
    
    def __init__(self, ttl_seconds: int = 5):
        self.ttl = ttl_seconds
        self.last_update = {}
        self.cache = {}
        self._lock = threading.Lock()
    
    def get_or_update(self, key: str, fetch_fn, force_refresh: bool = False):
        """Get cached value or fetch if expired."""
        with self._lock:
            now = time.time()
            
            if key in self.last_update and not force_refresh:
                if now - self.last_update[key] < self.ttl:
                    return self.cache.get(key)
            
            try:
                value = fetch_fn()
                self.cache[key] = value
                self.last_update[key] = now
                return value
            except Exception as e:
                log.error(f"Error fetching {key}: {e}")
                return self.cache.get(key)

metrics_cache = SystemMetricsCache(ttl_seconds=5)


# ── IMPROVED HEALTH CHECK WITH EXPONENTIAL BACKOFF ──────────
def start_backend_with_healthcheck(backend_main: Path, max_retries: int = 30) -> Optional[subprocess.Popen]:
    """Start backend with exponential backoff health checks. Much faster than blocking 30s loop."""
    _backend_proc = subprocess.Popen(
        [sys.executable, str(backend_main)],
        cwd=str(BACKEND_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    )
    log.info(f"Backend started — PID {_backend_proc.pid}")
    
    health_url = "http://127.0.0.1:8000/health"
    backoff_time = 0.1
    max_backoff = 2.0
    
    for attempt in range(max_retries):
        if _backend_proc.poll() is not None:
            log.error(f"Backend exited early with code {_backend_proc.returncode}")
            return None
        
        try:
            with urllib.request.urlopen(health_url, timeout=1) as res:
                if res.status == 200:
                    log.info("Backend health check passed ✓")
                    return _backend_proc
        except Exception:
            pass
        
        time.sleep(backoff_time)
        backoff_time = min(backoff_time * 1.5, max_backoff)
    
    log.warning("Backend health check timeout; continuing startup.")
    return _backend_proc


# ── BACKEND PROCESS MANAGEMENT ──────────────────────────────
_backend_proc: Optional[subprocess.Popen] = None
_backend_lock = threading.Lock()

def start_backend():
    """Start backend in background thread."""
    global _backend_proc
    try:
        backend_main = BACKEND_DIR / 'main.py'
        if not backend_main.exists():
            backend_main = BACKEND_DIR / 'app' / 'main.py'
        if not backend_main.exists():
            log.warning("Backend main.py not found — running without API")
            return
        
        with _backend_lock:
            _backend_proc = start_backend_with_healthcheck(backend_main)
    except Exception as e:
        log.error(f"Backend failed to start: {e}")

def stop_backend():
    """Gracefully stop backend process."""
    global _backend_proc
    with _backend_lock:
        if _backend_proc:
            try:
                _backend_proc.terminate()
                _backend_proc.wait(timeout=5)
                log.info("Backend stopped.")
            except subprocess.TimeoutExpired:
                _backend_proc.kill()
                log.warning("Backend force-killed after timeout")
            except Exception as e:
                log.error(f"Error stopping backend: {e}")
            finally:
                _backend_proc = None

atexit.register(stop_backend)


# ── DEPENDENCIES CHECK ───────────────────────────────────────
def check_deps():
    """Check required dependencies."""
    missing = []
    for pkg in ['webview']:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        log.warning(f"Missing packages: {missing}. Run: pip install {' '.join(missing)}")
    return len(missing) == 0

try:
    import webview
    WEBVIEW_OK = True
except ImportError:
    WEBVIEW_OK = False
    log.error("pywebview not installed. Run: pip install pywebview")


# ── PYWEBVIEW API ────────────────────────────────────────────
class IgrisAPI:
    """JavaScript ↔ Python bridge."""

    def __init__(self):
        self._dashboard_window = None
        self._orb_window       = None

    def set_windows(self, dash_win, orb_win):
        self._dashboard_window = dash_win
        self._orb_window       = orb_win

    def show_dashboard(self):
        if self._dashboard_window:
            self._dashboard_window.show()
            self._dashboard_window.restore()

    def hide_dashboard(self):
        if self._dashboard_window:
            self._dashboard_window.hide()

    def show_orb(self):
        if self._orb_window:
            self._orb_window.show()
            self._orb_window.restore()

    def hide_orb(self):
        if self._orb_window:
            self._orb_window.hide()

    def close_orb(self):
        if self._orb_window:
            self._orb_window.hide()

    def get_system_info(self, force_refresh: bool = False):
        """Return basic system info with caching instead of blocking calls."""
        def fetch_stats():
            try:
                import psutil
                return {
                    'cpu':    psutil.cpu_percent(interval=0),
                    'memory': psutil.virtual_memory().percent,
                    'disk':   psutil.disk_usage('/').percent,
                }
            except ImportError:
                return {'cpu': 0, 'memory': 0, 'disk': 0}
        
        return metrics_cache.get_or_update('system_info', fetch_stats, force_refresh)

    def quit(self):
        stop_backend()
        if webview.windows:
            webview.windows[0].destroy()

    def open_orb_from_hotkey(self):
        self.show_orb()
        if self._orb_window:
            self._orb_window.evaluate_js("vibrate();")


# ── HOTKEY LISTENER ────────────────────────────────────────
def start_hotkey_listener(api: IgrisAPI):
    try:
        import keyboard
        def on_hotkey():
            log.info("Global hotkey triggered — showing orb")
            api.open_orb_from_hotkey()
        keyboard.add_hotkey('ctrl+space', on_hotkey)
        log.info("Global hotkey: Ctrl+Space → IGRIS Orb")
        keyboard.wait()
    except ImportError:
        log.warning("keyboard package not installed — no global hotkey. Run: pip install keyboard")
    except Exception as e:
        log.error(f"Hotkey listener error: {e}")


# ── ICON PATH ────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_icon():
    for name in ['igris.ico', 'igris.png', 'icon.ico']:
        p = ASSETS_DIR / name
        if p.exists():
            return str(p)
    return None


# ── MAIN ─────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("  SIKANDER OS — IGRIS  v2.0 (OPTIMIZED)")
    log.info("  Starting application…")
    log.info("=" * 60)

    if not WEBVIEW_OK:
        print("\n[ERROR] pywebview not installed.")
        print("Run: pip install pywebview\n")
        input("Press Enter to exit…")
        sys.exit(1)

    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()

    api = IgrisAPI()
    icon = get_icon()

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
        background_color = '#000000',
        hidden           = True,
    )

    api.set_windows(dash_win, orb_win)

    hk_thread = threading.Thread(
        target=start_hotkey_listener,
        args=(api,),
        daemon=True
    )
    hk_thread.start()

    log.info("Launching webview over local HTTP server…")
    webview.start(
        debug     = '--debug' in sys.argv,
        icon      = icon,
        private_mode = False,
        http_server = True,
    )

    stop_backend()
    log.info("IGRIS shutdown complete.")


if __name__ == '__main__':
    main()
