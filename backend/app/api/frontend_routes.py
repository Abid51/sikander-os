"""
Frontend Modification + Live View API Routes
=============================================
Exposes all FrontendEngine and LiveViewEngine capabilities as REST + WebSocket
endpoints that Igris (or any frontend client) can call.

REST endpoints
--------------
GET  /frontend/files                – list all editable source files
GET  /frontend/read?path=App.tsx    – read a file's content
POST /frontend/write                – overwrite a file (with auto-backup)
POST /frontend/patch                – targeted find/replace in a file
POST /frontend/inject-component     – inject new React component into App.tsx
POST /frontend/redesign-theme       – replace index.css completely
GET  /frontend/design-state         – current tabs, colors, font snapshot
POST /frontend/rollback             – rollback a modification by id
GET  /frontend/history              – modification history

GET  /frontend/snapshot             – one-shot PC screenshot → base64 JPEG
GET  /frontend/windows              – list visible windows on this PC
GET  /frontend/live-view/stats      – streaming stats
POST /frontend/live-view/control    – pause / resume / set fps / set quality

WS   /frontend/ws/live              – WebSocket live screen stream (JPEG frames)
WS   /frontend/ws/modifications     – WebSocket push notification on every file change
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse

from app.core import api_auth
from app.core.frontend_engine import get_frontend_engine
from app.core.live_view import get_live_view

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/frontend", tags=["frontend-engine"])

# ── Modification notify hub ───────────────────────────────────────────────────
# Any number of WS clients can subscribe to modification events.

_mod_subscribers: Set[WebSocket] = set()


async def _require_ws_auth(websocket: WebSocket) -> bool:
    auth = websocket.headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    supplied = (
        websocket.headers.get("x-igris-token")
        or websocket.query_params.get("token")
        or bearer
    )
    if api_auth.verify_ws_token(supplied):
        return True
    await websocket.close(code=4401)
    return False


async def _notify_modification(event: Dict[str, Any]) -> None:
    dead = set()
    for ws in list(_mod_subscribers):
        try:
            await ws.send_json(event)
        except Exception:
            dead.add(ws)
    _mod_subscribers -= dead


# ── Frontend Engine endpoints ─────────────────────────────────────────────────

@router.get("/files")
async def list_files():
    """List all editable frontend source files."""
    return get_frontend_engine().list_files()


@router.get("/read")
async def read_file(path: str = Query(..., description="Relative path from frontend/src, e.g. 'App.tsx'")):
    """Read a frontend source file."""
    return get_frontend_engine().read_file(path)


@router.post("/write")
async def write_file(data: Dict[str, Any]):
    """
    Overwrite a file with new content.
    Body: { "path": "App.tsx", "content": "...", "reason": "optional note" }
    """
    result = get_frontend_engine().write_file(
        relative_path=data.get("path", ""),
        new_content=data.get("content", ""),
        reason=data.get("reason", ""),
    )
    if result.get("status") == "success":
        await _notify_modification({"type": "file_written", **result})
    return result


@router.post("/patch")
async def patch_file(data: Dict[str, Any]):
    """
    Targeted find-and-replace inside a file.
    Body: { "path": "App.tsx", "find": "...", "replace": "...", "reason": "..." }
    """
    result = get_frontend_engine().patch_file(
        relative_path=data.get("path", ""),
        find_text=data.get("find", ""),
        replace_text=data.get("replace", ""),
        reason=data.get("reason", ""),
    )
    if result.get("status") == "success":
        await _notify_modification({"type": "file_patched", **result})
    return result


@router.post("/inject-component")
async def inject_component(data: Dict[str, Any]):
    """
    Inject a new React component into App.tsx and wire it to the Sidebar.
    Body: {
        "component_name": "SystemAnalytics",
        "component_tsx": "const SystemAnalytics = () => <div>…</div>",
        "add_to_sidebar": true,
        "tab_icon": "BarChart2",
        "tab_label": "Analytics"
    }
    """
    result = get_frontend_engine().inject_component(
        component_name=data.get("component_name", "NewComponent"),
        component_tsx=data.get("component_tsx", ""),
        add_to_sidebar=data.get("add_to_sidebar", True),
        tab_icon=data.get("tab_icon", "Sparkles"),
        tab_label=data.get("tab_label", ""),
    )
    if result.get("status") == "success":
        await _notify_modification({"type": "component_injected", "component": data.get("component_name"), **result})
    return result


@router.post("/redesign-theme")
async def redesign_theme(data: Dict[str, Any]):
    """
    Replace the entire CSS theme (index.css).
    Body: { "css": "/* new CSS */" , "reason": "dark cyberpunk redesign" }
    """
    result = get_frontend_engine().redesign_theme(
        new_css=data.get("css", ""),
        reason=data.get("reason", "theme redesign"),
    )
    if result.get("status") == "success":
        await _notify_modification({"type": "theme_redesigned", **result})
    return result


@router.get("/design-state")
async def design_state():
    """Return high-level snapshot of current frontend design (tabs, colors, font)."""
    return get_frontend_engine().get_design_state()


@router.post("/rollback")
async def rollback(data: Dict[str, Any]):
    """
    Rollback a specific modification.
    Body: { "modification_id": 3 }
    """
    result = get_frontend_engine().rollback(data.get("modification_id", 0))
    if result.get("status") == "success":
        await _notify_modification({"type": "rollback", **result})
    return result


@router.get("/history")
async def get_history(limit: int = Query(20)):
    """Return modification history."""
    return {
        "history": get_frontend_engine().get_history(limit),
        "total": len(get_frontend_engine().modification_history),
    }


# ── Live View REST endpoints ──────────────────────────────────────────────────

@router.get("/snapshot")
async def take_snapshot(window: str = Query("", description="Window title substring to capture (empty = full screen)")):
    """
    Take an instant screenshot of the PC (or a specific window).
    Returns a base64-encoded JPEG image.
    """
    lv = get_live_view()
    frame_b64 = await lv.snapshot(window_title=window)
    if frame_b64 is None:
        return JSONResponse(
            status_code=503,
            content={"error": "Screen capture unavailable. Install: pip install mss Pillow"}
        )
    return {
        "status": "ok",
        "format": "jpeg",
        "frame_b64": frame_b64,
        "note": "Render this as <img src='data:image/jpeg;base64,{frame_b64}' />"
    }


@router.get("/windows")
async def list_windows():
    """List all currently visible windows on this PC."""
    return {
        "windows": get_live_view().list_windows(),
        "note": "Install pygetwindow for window-specific capture: pip install pygetwindow"
    }


@router.get("/live-view/stats")
async def live_view_stats():
    """Return current live-stream statistics."""
    return get_live_view().get_stats()


@router.post("/live-view/control")
async def live_view_control(data: Dict[str, Any]):
    """
    Control the live view stream.
    Body: { "action": "pause"|"resume"|"set_fps"|"set_quality", "value": <int> }
    """
    lv = get_live_view()
    action = data.get("action", "")
    value = data.get("value")

    if action == "pause":
        lv.pause()
        return {"status": "ok", "action": "paused"}
    elif action == "resume":
        lv.resume()
        return {"status": "ok", "action": "resumed"}
    elif action == "set_fps" and value is not None:
        lv.set_fps(int(value))
        return {"status": "ok", "fps": lv.fps}
    elif action == "set_quality" and value is not None:
        lv.set_quality(int(value))
        return {"status": "ok", "quality": lv.quality}
    else:
        return {"status": "error", "message": "Unknown action or missing value"}


# ── WebSocket: Live Screen Stream ─────────────────────────────────────────────

@router.websocket("/ws/live")
async def ws_live_stream(websocket: WebSocket):
    """
    WebSocket endpoint for live PC screen stream.
    Client receives: { "type": "live_frame", "frame": "<base64 JPEG>", "timestamp": <float> }
    Client can send: { "action": "pause"|"resume"|"set_fps", "value": 10 }
    """
    if not await _require_ws_auth(websocket):
        return
    await websocket.accept()
    lv = get_live_view()
    lv.add_client(websocket)

    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
                action = msg.get("action", "")
                if action == "pause":
                    lv.pause()
                elif action == "resume":
                    lv.resume()
                elif action == "set_fps":
                    lv.set_fps(int(msg.get("value", 8)))
                elif action == "set_quality":
                    lv.set_quality(int(msg.get("value", 65)))
            except asyncio.TimeoutError:
                # Keep-alive heartbeat
                try:
                    await websocket.send_json({"type": "heartbeat", "clients": len(lv._clients)})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"[LiveView WS] error: {e}")
    finally:
        lv.remove_client(websocket)
        logger.info("[LiveView WS] client disconnected")


# ── WebSocket: Modification Notifications ─────────────────────────────────────

@router.websocket("/ws/modifications")
async def ws_modifications(websocket: WebSocket):
    """
    WebSocket that pushes a notification every time Igris modifies a frontend file.
    Useful for the frontend to auto-refresh after a hot-reload.
    """
    if not await _require_ws_auth(websocket):
        return
    await websocket.accept()
    _mod_subscribers.add(websocket)
    try:
        await websocket.send_json({"type": "connected", "message": "Watching frontend modifications…"})
        while True:
            # Just keep the connection alive; notifications are pushed from write/patch/inject calls
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        _mod_subscribers.discard(websocket)
