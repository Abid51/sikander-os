"""
Live View Engine for Igris AI
==============================
Captures the PC screen in real-time and streams compressed JPEG frames
over WebSocket as base64 strings so the frontend can show a live feed.

Also supports:
  - One-shot screenshot → base64 (for REST endpoint)
  - Window-specific capture (by title substring)
  - Pause / resume streaming
  - Adjustable FPS and quality

Dependencies (auto-detected, graceful fallback):
  pip install pillow mss pygetwindow
"""

import asyncio
import base64
import io
import logging
import time
from typing import Optional, Set, Dict, Any

logger = logging.getLogger(__name__)

# ── Optional imports ──────────────────────────────────────────────────────────

try:
    import mss
    _MSS_AVAILABLE = True
except ImportError:
    _MSS_AVAILABLE = False
    logger.warning("[LiveView] 'mss' not installed. Install via: pip install mss")

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    logger.warning("[LiveView] 'Pillow' not installed. Install via: pip install Pillow")

try:
    import pygetwindow as gw
    _GW_AVAILABLE = True
except ImportError:
    _GW_AVAILABLE = False


# ── Frame Capture ─────────────────────────────────────────────────────────────

class ScreenCapture:
    """Low-level screen / window capture using mss + Pillow."""

    def __init__(self, quality: int = 70, scale: float = 0.75):
        """
        quality : JPEG quality (1-95)
        scale   : downscale factor (0.5 = half resolution → faster)
        """
        self.quality = quality
        self.scale = scale

    def capture_full(self) -> Optional[bytes]:
        """Capture entire primary monitor → JPEG bytes."""
        if not (_MSS_AVAILABLE and _PIL_AVAILABLE):
            return None
        with mss.mss() as sct:
            monitor = sct.monitors[1]          # monitor[0] = all, [1] = primary
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return self._encode(img)

    def capture_window(self, title_substr: str) -> Optional[bytes]:
        """Capture a specific window by title substring."""
        if not _GW_AVAILABLE:
            return self.capture_full()          # fallback to full screen
        wins = [w for w in gw.getAllWindows() if title_substr.lower() in w.title.lower() and w.visible]
        if not wins:
            return self.capture_full()
        w = wins[0]
        region = {"left": w.left, "top": w.top, "width": w.width, "height": w.height}
        if not (_MSS_AVAILABLE and _PIL_AVAILABLE):
            return None
        with mss.mss() as sct:
            raw = sct.grab(region)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return self._encode(img)

    def _encode(self, img: "Image.Image") -> bytes:
        if self.scale != 1.0:
            new_w = int(img.width * self.scale)
            new_h = int(img.height * self.scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=self.quality, optimize=True)
        return buf.getvalue()

    def capture_b64(self, window_title: str = "") -> Optional[str]:
        """Return a base64-encoded JPEG string (for REST endpoints)."""
        raw = self.capture_window(window_title) if window_title else self.capture_full()
        if raw is None:
            return None
        return base64.b64encode(raw).decode("utf-8")


# ── Streaming Controller ──────────────────────────────────────────────────────

class LiveViewEngine:
    """
    Manages WebSocket clients that want a live screen stream.
    Call `add_client(ws)` / `remove_client(ws)` from a WebSocket route.
    The streaming loop runs as a background asyncio task.
    """

    def __init__(self, fps: int = 8, quality: int = 65, scale: float = 0.70):
        self.fps = fps
        self.quality = quality
        self.scale = scale
        self._capture = ScreenCapture(quality=quality, scale=scale)
        self._clients: Set = set()
        self._task: Optional[asyncio.Task] = None
        self._paused = False
        self._latest_frame_b64: Optional[str] = None
        self._latest_frame_ts: Optional[float] = None
        self._stats: Dict[str, Any] = {
            "frames_sent": 0,
            "clients": 0,
            "running": False,
            "fps": fps,
            "quality": quality,
            "scale": scale,
        }

    # ── Client management ─────────────────────────────────────────────────────

    def add_client(self, ws) -> None:
        self._clients.add(ws)
        self._stats["clients"] = len(self._clients)
        self._ensure_running()

    def remove_client(self, ws) -> None:
        self._clients.discard(ws)
        self._stats["clients"] = len(self._clients)

    # ── Controls ──────────────────────────────────────────────────────────────

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def set_fps(self, fps: int) -> None:
        self.fps = max(1, min(fps, 30))
        self._stats["fps"] = self.fps

    def set_quality(self, quality: int) -> None:
        self.quality = max(10, min(quality, 95))
        self._capture.quality = self.quality
        self._stats["quality"] = self.quality

    def get_stats(self) -> Dict[str, Any]:
        self._stats["running"] = self._task is not None and not self._task.done()
        self._stats["has_latest_frame"] = self._latest_frame_b64 is not None
        self._stats["latest_frame_ts"] = self._latest_frame_ts
        return self._stats

    def get_latest_frame(self) -> Optional[dict]:
        """Return latest captured frame metadata + base64 payload."""
        if not self._latest_frame_b64:
            return None
        return {
            "frame_b64": self._latest_frame_b64,
            "timestamp": self._latest_frame_ts,
            "format": "jpeg",
        }

    # ── Streaming loop ────────────────────────────────────────────────────────

    def _ensure_running(self) -> None:
        if self._task is None or self._task.done():
            try:
                loop = asyncio.get_event_loop()
                self._task = loop.create_task(self._stream_loop())
                self._stats["running"] = True
                logger.info("[LiveView] Stream loop started")
            except RuntimeError:
                logger.warning("[LiveView] No running event loop – stream not started")

    async def _stream_loop(self) -> None:
        interval = 1.0 / self.fps
        while self._clients:
            t0 = time.monotonic()

            if not self._paused:
                frame_bytes = await asyncio.get_event_loop().run_in_executor(
                    None, self._capture.capture_full
                )
                if frame_bytes:
                    b64 = base64.b64encode(frame_bytes).decode("utf-8")
                    self._latest_frame_b64 = b64
                    self._latest_frame_ts = time.time()
                    payload = {
                        "type": "live_frame",
                        "frame": b64,
                        "format": "jpeg",
                        "timestamp": time.time(),
                        "clients": len(self._clients),
                    }
                    dead = set()
                    for ws in list(self._clients):
                        try:
                            await ws.send_json(payload)
                            self._stats["frames_sent"] += 1
                        except Exception:
                            dead.add(ws)
                    self._clients -= dead
                    self._stats["clients"] = len(self._clients)

            elapsed = time.monotonic() - t0
            await asyncio.sleep(max(0, (1.0 / self.fps) - elapsed))

        self._stats["running"] = False
        self._task = None
        logger.info("[LiveView] Stream loop stopped (no clients)")

    # ── One-shot REST capture ────────────────────────────────────────────────

    async def snapshot(self, window_title: str = "") -> Optional[str]:
        """Async-friendly one-shot screenshot → base64 JPEG."""
        frame = await asyncio.get_event_loop().run_in_executor(
            None, self._capture.capture_b64, window_title
        )
        if frame:
            self._latest_frame_b64 = frame
            self._latest_frame_ts = time.time()
        return frame

    # ── Available windows list ────────────────────────────────────────────────

    def list_windows(self) -> list:
        if not _GW_AVAILABLE:
            return []
        return [{"title": w.title, "visible": w.visible} for w in gw.getAllWindows() if w.title.strip()]


# ── Singleton ─────────────────────────────────────────────────────────────────

_live_view: Optional[LiveViewEngine] = None


def get_live_view() -> LiveViewEngine:
    global _live_view
    if _live_view is None:
        _live_view = LiveViewEngine()
    return _live_view
