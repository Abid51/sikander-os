"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS WEBSOCKET HUB — Real-time Communication Center
  Features: Streaming chat, live system metrics, daemon events,
            multi-room broadcast, connection management
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

import psutil
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.daemon_master import daemon_master
from app.core import api_auth

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


# ─────────────────────────────────────────────────────────────────────────────
#  CONNECTION MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class ConnectionManager:
    """Manages WebSocket connections with room-based broadcasting."""

    def __init__(self) -> None:
        self._connections: Dict[str, WebSocket] = {}        # id -> ws
        self._rooms: Dict[str, Set[str]] = defaultdict(set) # room -> {conn_ids}
        self._metadata: Dict[str, dict] = {}                # id -> info
        self._stats = {"total_connections": 0, "total_messages": 0, "peak_concurrent": 0}

    async def connect(self, websocket: WebSocket, room: str = "general") -> str:
        await websocket.accept()
        conn_id = str(uuid.uuid4())[:8]
        self._connections[conn_id] = websocket
        self._rooms[room].add(conn_id)
        self._metadata[conn_id] = {
            "room": room,
            "connected_at": time.time(),
            "messages_sent": 0,
            "messages_received": 0,
        }
        self._stats["total_connections"] += 1
        concurrent = len(self._connections)
        if concurrent > self._stats["peak_concurrent"]:
            self._stats["peak_concurrent"] = concurrent

        logger.info(f"[WS HUB] Client {conn_id} connected to room '{room}' ({concurrent} active)")
        return conn_id

    def disconnect(self, conn_id: str) -> None:
        meta = self._metadata.pop(conn_id, {})
        room = meta.get("room", "general")
        self._rooms[room].discard(conn_id)
        self._connections.pop(conn_id, None)
        logger.info(f"[WS HUB] Client {conn_id} disconnected ({len(self._connections)} active)")

    async def send_personal(self, conn_id: str, data: dict) -> None:
        ws = self._connections.get(conn_id)
        if ws:
            try:
                await ws.send_json(data)
                if conn_id in self._metadata:
                    self._metadata[conn_id]["messages_sent"] += 1
                self._stats["total_messages"] += 1
            except Exception:
                self.disconnect(conn_id)

    async def broadcast_room(self, room: str, data: dict, exclude: str = "") -> None:
        dead: List[str] = []
        for cid in self._rooms.get(room, set()):
            if cid == exclude:
                continue
            ws = self._connections.get(cid)
            if ws:
                try:
                    await ws.send_json(data)
                    self._stats["total_messages"] += 1
                except Exception:
                    dead.append(cid)
        for cid in dead:
            self.disconnect(cid)

    async def broadcast_all(self, data: dict) -> None:
        dead: List[str] = []
        for cid, ws in self._connections.items():
            try:
                await ws.send_json(data)
                self._stats["total_messages"] += 1
            except Exception:
                dead.append(cid)
        for cid in dead:
            self.disconnect(cid)

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "active_connections": len(self._connections),
            "rooms": {r: len(ids) for r, ids in self._rooms.items() if ids},
        }


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

ws_manager = ConnectionManager()


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

# ─── Shared brain reference (set by main.py) ─────────────────────────────────
_brain = None

def set_brain(brain_instance):
    global _brain
    _brain = brain_instance


# ─────────────────────────────────────────────────────────────────────────────
#  1. STREAMING CHAT — /ws/chat
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    """
    Real-time chat with Igris brain.
    
    Send: {"type": "message", "text": "your command"}
    Receive: {"type": "stream_start"} → {"type": "token", "text": "..."} → {"type": "stream_end", "full_text": "..."}
    
    Also supports:
      {"type": "history"} — get chat history
      {"type": "clear"}   — clear history
    """
    if not await _require_ws_auth(websocket):
        return
    conn_id = await ws_manager.connect(websocket, "chat")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"type": "message", "text": raw}

            msg_type = data.get("type", "message")

            if msg_type == "message":
                text = data.get("text", "").strip()
                if not text:
                    continue

                if _brain:
                    # Send stream_start
                    await ws_manager.send_personal(conn_id, {
                        "type": "stream_start",
                        "timestamp": time.time(),
                    })

                    # Process through brain
                    try:
                        result = await _brain.process_command(text)
                        full_text = result.get("text", "")
                        emotion = result.get("emotion", "calm")

                        # Simulate streaming by sending word chunks
                        words = full_text.split()
                        buffer = ""
                        for i, word in enumerate(words):
                            buffer += word + " "
                            await ws_manager.send_personal(conn_id, {
                                "type": "token",
                                "text": word + " ",
                                "index": i,
                            })
                            await asyncio.sleep(0.02)  # 20ms per word

                        await ws_manager.send_personal(conn_id, {
                            "type": "stream_end",
                            "full_text": full_text,
                            "emotion": emotion,
                            "audio_sync": result.get("audio_sync", []),
                            "timestamp": time.time(),
                        })
                    except Exception as e:
                        await ws_manager.send_personal(conn_id, {
                            "type": "error",
                            "error": str(e),
                        })
                else:
                    await ws_manager.send_personal(conn_id, {
                        "type": "error",
                        "error": "Brain not initialized",
                    })

            elif msg_type == "history":
                if _brain:
                    await ws_manager.send_personal(conn_id, {
                        "type": "history",
                        "data": _brain.memory.get("history", [])[-20:],
                    })

            elif msg_type == "clear":
                if _brain:
                    _brain.memory["history"] = []
                    _brain.save_memory()
                    await ws_manager.send_personal(conn_id, {
                        "type": "cleared",
                    })

            elif msg_type == "ping":
                await ws_manager.send_personal(conn_id, {"type": "pong", "ts": time.time()})

    except WebSocketDisconnect:
        ws_manager.disconnect(conn_id)


# ─────────────────────────────────────────────────────────────────────────────
#  2. LIVE SYSTEM MONITOR — /ws/monitor
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/monitor")
async def ws_monitor(websocket: WebSocket):
    """
    Real-time system metrics stream.
    Sends CPU/memory/disk/network stats every 2 seconds.
    
    Send: {"interval": 3} to change update interval (1-30s)
    """
    if not await _require_ws_auth(websocket):
        return
    conn_id = await ws_manager.connect(websocket, "monitor")
    interval = 2.0
    _prev_net = psutil.net_io_counters()

    try:
        while True:
            # Build metrics snapshot
            cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            net = psutil.net_io_counters()
            
            # Calculate network speed
            net_sent_speed = (net.bytes_sent - _prev_net.bytes_sent) / interval
            net_recv_speed = (net.bytes_recv - _prev_net.bytes_recv) / interval
            _prev_net = net

            # Top 5 CPU processes
            top_procs = []
            for p in sorted(
                psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
                key=lambda x: x.info.get("cpu_percent") or 0,
                reverse=True,
            )[:5]:
                top_procs.append({
                    "pid": p.info["pid"],
                    "name": p.info["name"],
                    "cpu": p.info.get("cpu_percent", 0),
                    "mem": round(p.info.get("memory_percent", 0), 1),
                })

            payload = {
                "type": "metrics",
                "timestamp": time.time(),
                "cpu": {
                    "overall": sum(cpu_per_core) / len(cpu_per_core) if cpu_per_core else 0,
                    "per_core": cpu_per_core,
                    "cores": len(cpu_per_core),
                },
                "memory": {
                    "total_gb": round(mem.total / 1e9, 2),
                    "used_gb": round(mem.used / 1e9, 2),
                    "available_gb": round(mem.available / 1e9, 2),
                    "percent": mem.percent,
                },
                "disk": {
                    "total_gb": round(disk.total / 1e9, 2),
                    "used_gb": round(disk.used / 1e9, 2),
                    "free_gb": round(disk.free / 1e9, 2),
                    "percent": disk.percent,
                },
                "network": {
                    "sent_speed_mbps": round(net_sent_speed * 8 / 1e6, 2),
                    "recv_speed_mbps": round(net_recv_speed * 8 / 1e6, 2),
                    "total_sent_gb": round(net.bytes_sent / 1e9, 3),
                    "total_recv_gb": round(net.bytes_recv / 1e9, 3),
                },
                "top_processes": top_procs,
                "ws_stats": ws_manager.get_stats(),
            }

            await ws_manager.send_personal(conn_id, payload)

            # Check for interval adjustment
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=interval)
                msg = json.loads(raw)
                if "interval" in msg:
                    interval = max(1.0, min(30.0, float(msg["interval"])))
            except asyncio.TimeoutError:
                pass

    except WebSocketDisconnect:
        ws_manager.disconnect(conn_id)


# ─────────────────────────────────────────────────────────────────────────────
#  3. EVENT BUS — /ws/events
# ─────────────────────────────────────────────────────────────────────────────

class EventBus:
    """Central event bus for broadcasting system-wide events."""

    def __init__(self) -> None:
        self._history: List[dict] = []
        self._max_history = 500

    async def emit(self, event_type: str, data: Any = None, severity: str = "info") -> None:
        event = {
            "type": "event",
            "event_type": event_type,
            "data": data,
            "severity": severity,
            "timestamp": time.time(),
            "id": str(uuid.uuid4())[:8],
        }
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        # Broadcast to all event subscribers
        await ws_manager.broadcast_room("events", event)

    def get_history(self, limit: int = 50, event_type: str = None) -> List[dict]:
        filtered = self._history
        if event_type:
            filtered = [e for e in filtered if e["event_type"] == event_type]
        return filtered[-limit:]


event_bus = EventBus()


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    """
    Subscribe to system-wide events (daemon alerts, errors, security, etc.)
    Receives all events broadcast via event_bus.emit()
    """
    if not await _require_ws_auth(websocket):
        return
    conn_id = await ws_manager.connect(websocket, "events")
    
    # Send recent history on connect
    await ws_manager.send_personal(conn_id, {
        "type": "event_history",
        "events": event_bus.get_history(20),
    })

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)

            if msg.get("type") == "get_history":
                limit = msg.get("limit", 50)
                evt_type = msg.get("event_type")
                await ws_manager.send_personal(conn_id, {
                    "type": "event_history",
                    "events": event_bus.get_history(limit, evt_type),
                })
            elif msg.get("type") == "ping":
                await ws_manager.send_personal(conn_id, {"type": "pong"})

    except WebSocketDisconnect:
        ws_manager.disconnect(conn_id)


# ─────────────────────────────────────────────────────────────────────────────
#  REST ENDPOINTS FOR WS STATS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/ws/stats")
async def get_ws_stats():
    """Get WebSocket connection statistics."""
    return ws_manager.get_stats()

@router.get("/ws/events/history")
async def get_event_history(limit: int = 50, event_type: str = None):
    """Get event history via REST."""
    return {"events": event_bus.get_history(limit, event_type)}

@router.post("/ws/broadcast")
async def broadcast_message(data: dict):
    """Broadcast a message to all connected clients."""
    room = data.get("room", "")
    message = data.get("message", {})
    if room:
        await ws_manager.broadcast_room(room, message)
    else:
        await ws_manager.broadcast_all(message)
    return {"status": "broadcast_sent", "active_connections": len(ws_manager._connections)}


@router.websocket("/ws/collaboration")
async def collaboration_handler(websocket: WebSocket):
    """
    Collaborative session handler — multi-user real-time coordination.
    All messages broadcast to everyone in the 'collaboration' room.
    """
    if not await _require_ws_auth(websocket):
        return
    conn_id = await ws_manager.connect(websocket, "collaboration")

    # Register user with Iron Crown daemon (if available)
    iron_crown = daemon_master.get_daemon("Iron Crown")
    if iron_crown and hasattr(iron_crown, "register_user"):
        iron_crown.register_user(conn_id)

    try:
        while True:
            data = await websocket.receive_text()
            # Broadcast to all users in collaboration room (except sender)
            await ws_manager.broadcast_room(
                "collaboration",
                {"type": "message", "user_id": conn_id, "data": data, "timestamp": time.time()},
                exclude=conn_id,
            )
    except WebSocketDisconnect:
        ws_manager.disconnect(conn_id)
        if iron_crown and hasattr(iron_crown, "unregister_user"):
            iron_crown.unregister_user(conn_id)
