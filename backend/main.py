from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field
import uvicorn
import psutil
import json
import asyncio
import sys
import os
import multiprocessing

# Windows consoles often use cp1252; avoid UnicodeEncodeError from log prints with emoji.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import time
import logging
import uuid
import shutil
from datetime import datetime
from pathlib import Path

# Load backend/.env before any app imports (dev: auto-create from .env.example if missing).
_backend_dir = Path(__file__).resolve().parent
_env_path = _backend_dir / ".env"
_env_example = _backend_dir / ".env.example"
if not _env_path.is_file() and _env_example.is_file():
    try:
        shutil.copyfile(_env_example, _env_path)
    except OSError:
        pass
from dotenv import load_dotenv

load_dotenv(dotenv_path=_env_path, override=False)

from app.core import metrics as app_metrics
from app.core import observability
from app.core import api_auth
from app.core.job_queue import start_worker as start_job_worker, queue_depth as job_queue_depth

from app.core.ai_core import IgrisBrain
from app.system.os_control import SystemController
from app.api import ws_hub
from app.api.router_setup import wire_shared_dependencies, register_all_routers
from app.core.database import db
from app.core.monitoring import performance_monitor, analytics, health_check
from app.core.security import security_manager, audit_logger
from app.core.task_orchestrator import task_orchestrator
from app.core.advanced_logging import advanced_logger, EventType
from app.core.command_suggester import command_suggester
from app.core.self_healing import ErrorHandler, RecoveryAction, RecoveryStrategy
from app.core.advanced_monitoring import advanced_monitor, AdvancedMonitor
from app.core.daemon_master import daemon_master


def _disk_usage_root() -> str:
    """Cross-platform root path for psutil.disk_usage."""
    if os.name == "nt":
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"


# Neural Memory
try:
    from app.memory.vector_memory import get_neural_memory
    neural_memory = get_neural_memory()
except Exception as e:
    logging.critical(f"Neural Memory initialization failed: {str(e)}", exc_info=True)
    neural_memory = None
    # Fallback to basic memory system
    from app.memory.fallback_memory import FallbackMemory
    neural_memory = FallbackMemory()

# Self-Healing Engine
try:
    from app.core.self_healing import get_self_healing_engine
    healer = get_self_healing_engine()
except Exception as e:
    logging.critical(f"Self-Healing Engine initialization failed: {str(e)}", exc_info=True)
    healer = None
    # Fallback to basic error handling
    from app.core.fallback_error_handler import FallbackErrorHandler
    healer = FallbackErrorHandler()

# Emotional Intelligence
try:
    from app.core.emotional_intelligence import get_emotional_engine
    emotional_ai = get_emotional_engine()
except Exception as _e:
    print(f"[MAIN] Emotional AI unavailable: {_e}")
    emotional_ai = None

# Predictive Engine
try:
    from app.core.predictive_engine import get_predictive_engine
    predictor = get_predictive_engine()
except Exception as _e:
    print(f"[MAIN] Predictive Engine unavailable: {_e}")
    predictor = None

# Quantum Vault
try:
    from app.memory.quantum_vault import get_quantum_vault
    vault = get_quantum_vault()
except Exception as _e:
    print(f"[MAIN] Quantum Vault unavailable: {_e}")
    vault = None

# ── Phase 5: God-Tier Supremacy Engines ──────────────────────────────────────

try:
    from app.core.quantum_thinking_engine import get_quantum_thinking_engine
    quantum_brain = get_quantum_thinking_engine()
except Exception as _e:
    print(f"[MAIN] Quantum Thinking / Decision engine unavailable: {_e}")
    quantum_brain = None

try:
    from app.core.digital_genome import get_digital_genome
    genome = get_digital_genome()
except Exception as _e:
    print(f"[MAIN] Digital Genome unavailable: {_e}")
    genome = None

try:
    from app.core.reality_anchor import get_reality_anchor
    reality_anchor = get_reality_anchor()
except Exception as _e:
    print(f"[MAIN] Reality Anchor unavailable: {_e}")
    reality_anchor = None

try:
    from app.core.cognitive_load import get_cognitive_load_balancer
    cognitive_load = get_cognitive_load_balancer()
except Exception as _e:
    print(f"[MAIN] Cognitive Load unavailable: {_e}")
    cognitive_load = None

try:
    from app.core.oracle_protocol import get_oracle_protocol
    oracle = get_oracle_protocol()
except Exception as _e:
    print(f"[MAIN] Oracle unavailable: {_e}")
    oracle = None

try:
    from app.memory.knowledge_graph import get_knowledge_graph
    knowledge_graph = get_knowledge_graph()
except Exception as _e:
    print(f"[MAIN] Knowledge Graph unavailable: {_e}")
    knowledge_graph = None

try:
    from app.core.parallel_universe import get_parallel_universe_tester
    parallel_universe = get_parallel_universe_tester()
except Exception as _e:
    print(f"[MAIN] Parallel Universe unavailable: {_e}")
    parallel_universe = None

try:
    from app.core.shadow_protocol import get_shadow_protocol
    shadow_proto = get_shadow_protocol()
except Exception as _e:
    print(f"[MAIN] Shadow Protocol unavailable: {_e}")
    shadow_proto = None

try:
    from app.core.consciousness_git import get_consciousness_git
    consciousness_git = get_consciousness_git()
except Exception as _e:
    print(f"[MAIN] Consciousness Git unavailable: {_e}")
    consciousness_git = None

try:
    from app.agents.economic_engine import get_economic_engine
    economic_engine = get_economic_engine()
except Exception as _e:
    print(f"[MAIN] Economic Engine unavailable: {_e}")
    economic_engine = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _is_production_env() -> bool:
    env = os.getenv("IGRIS_ENV") or os.getenv("ENV") or os.getenv("APP_ENV") or ""
    return env.strip().lower() in {"prod", "production"}


def _cors_allow_origins() -> list[str]:
    raw = os.getenv("IGRIS_CORS_ORIGINS", "").strip()
    if raw:
        return [v.strip() for v in raw.split(",") if v.strip()]
    if _is_production_env():
        return []
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def _enforce_sensitive_route_auth(request: Request) -> None:
    """
    Require token auth to be enabled and valid for high-risk routes.
    This prevents sensitive actions from running in open/dev auth mode.
    """
    if not api_auth.is_auth_enabled():
        raise HTTPException(
            status_code=503,
            detail="Sensitive route disabled until IGRIS_API_TOKEN is configured.",
        )
    if not api_auth.verify_request(request):
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Phase 6: Unstoppable God Systems ──────────────────────────────────────────

try:
    from app.core.thought_crystallizer import get_crystallizer
    crystallizer = get_crystallizer()
except Exception as _e:
    print(f"[MAIN] Crystallizer unavailable: {_e}")
    crystallizer = None

try:
    from app.core.neural_reflex import get_neural_reflex
    neural_reflex = get_neural_reflex()
except Exception as _e:
    print(f"[MAIN] Neural Reflex unavailable: {_e}")
    neural_reflex = None

try:
    from app.core.dream_space import get_dream_space
    dream_space = get_dream_space()
except Exception as _e:
    print(f"[MAIN] Dream Space unavailable: {_e}")
    dream_space = None

try:
    from app.core.neural_lockdown import get_neural_lockdown
    neural_lockdown = get_neural_lockdown()
except Exception as _e:
    print(f"[MAIN] Neural Lockdown unavailable: {_e}")
    neural_lockdown = None

try:
    from app.core.system_dna import get_system_dna
    system_dna = get_system_dna()
except Exception as _e:
    print(f"[MAIN] System DNA unavailable: {_e}")
    system_dna = None

try:
    from app.core.singularity_dashboard import get_singularity_dashboard
    singularity = get_singularity_dashboard()
except Exception as _e:
    print(f"[MAIN] Singularity unavailable: {_e}")
    singularity = None

# ── Phase 7: Omega Tier Consciousness Systems ─────────────────────────────────

try:
    from app.core.meta_consciousness import get_meta_consciousness
    meta_consciousness = get_meta_consciousness()
except Exception as _e:
    print(f"[MAIN] Meta-Consciousness unavailable: {_e}")
    meta_consciousness = None

try:
    from app.core.temporal_memory import get_temporal_memory
    temporal_memory = get_temporal_memory()
except Exception as _e:
    print(f"[MAIN] Temporal Memory unavailable: {_e}")
    temporal_memory = None

try:
    from app.core.reality_distortion import get_reality_distortion
    reality_distortion = get_reality_distortion()
except Exception as _e:
    print(f"[MAIN] Reality Distortion unavailable: {_e}")
    reality_distortion = None

try:
    from app.core.psychographic import get_psychographic
    psychographic = get_psychographic()
except Exception as _e:
    print(f"[MAIN] Psychographic unavailable: {_e}")
    psychographic = None

try:
    from app.core.nemesis_protocol import get_nemesis_protocol
    nemesis = get_nemesis_protocol()
except Exception as _e:
    print(f"[MAIN] Nemesis Protocol unavailable: {_e}")
    nemesis = None

try:
    from app.core.context_compressor import get_context_compressor
    context_compressor = get_context_compressor()
except Exception as _e:
    print(f"[MAIN] Context Compressor unavailable: {_e}")
    context_compressor = None

try:
    from app.core.akashic_records import get_akashic_records
    akashic = get_akashic_records()
except Exception as _e:
    print(f"[MAIN] Akashic Records unavailable: {_e}")
    akashic = None

try:
    from app.core.quantum_backup import get_quantum_backup
    quantum_backup = get_quantum_backup()
except Exception as _e:
    print(f"[MAIN] Quantum Backup unavailable: {_e}")
    quantum_backup = None

try:
    from app.core.personality_theater import get_personality_theater
    personality_theater = get_personality_theater()
except Exception as _e:
    print(f"[MAIN] Personality Theater unavailable: {_e}")
    personality_theater = None

app = FastAPI(title="Knight Commander Igris The Bloodred API - Advanced Edition")


class DaemonCommandRequest(BaseModel):
    command: str = Field(..., min_length=1)
    params: dict = Field(default_factory=dict)
    args: dict = Field(default_factory=dict)


class DaemonEventRequest(BaseModel):
    target: str = Field(..., min_length=1)
    command: str = Field(..., min_length=1)
    params: dict = Field(default_factory=dict)


class ForgeDaemonRequest(BaseModel):
    class_name: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)


class BlockIPRequest(BaseModel):
    ip: str = Field(..., min_length=3)


class PortScanRequest(BaseModel):
    host: str = Field(..., min_length=1)
    port: int = Field(..., ge=1, le=65535)


class ScheduleTaskRequest(BaseModel):
    name: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    params: dict = Field(default_factory=dict)
    schedule: dict = Field(default_factory=dict)
    recurring: bool = False


class OCRRequest(BaseModel):
    image_path: str = Field(..., min_length=1)


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1)


class EconomyTradeRequest(BaseModel):
    symbol: str = "BTC/USDT"
    side: str = "buy"
    amount_usd: float = Field(default=100.0, gt=0)


class EconomyStreamRequest(BaseModel):
    name: str = Field(..., min_length=1)


class EconomyIncomeRequest(BaseModel):
    stream_name: str = Field(..., min_length=1)
    amount_usd: float = Field(..., gt=0)
    source: str = ""
    notes: str = ""
    metadata: dict = Field(default_factory=dict)

# Initialize error handler
error_handler = ErrorHandler()

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    if request.method == "OPTIONS":
        return await call_next(request)

    start_time = time.time()
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    rid_token = observability.set_request_id(rid)
    request.state.request_id = rid

    try:
        if not api_auth.verify_request(request):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized", "request_id": rid},
                headers={"X-Request-ID": rid},
            )

        app_metrics.inc("http_requests")

        # Check rate limit
        client_ip = request.client.host if request.client else "unknown"
        rate_limit_ok, rate_limit_info = security_manager.check_rate_limit(client_ip)

        if not rate_limit_ok:
            audit_logger.log_event("rate_limit_exceeded", None, {
                "ip": client_ip,
                "endpoint": request.url.path
            }, client_ip, "WARNING")
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "request_id": rid},
                headers={"X-Request-ID": rid},
            )

        # Process request
        response = await call_next(request)

        # Calculate response time
        response_time = (time.time() - start_time) * 1000

        # Record metrics
        advanced_monitor.record_operation(
            f"{request.method} {request.url.path}",
            response_time,
            "success" if response.status_code < 400 else "failed"
        )

        # Log API access
        db.log_api_access(
            user_id=None,  # Could extract from token
            endpoint=request.url.path,
            method=request.method,
            status_code=response.status_code,
            response_time_ms=int(response_time),
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent", "unknown")
        )

        # Record metrics
        performance_monitor.record_api_response_time(request.url.path, response_time)

        # Add security headers
        for header, value in security_manager.get_security_headers().items():
            response.headers[header] = value

        # Add rate limit headers
        response.headers["X-RateLimit-Remaining"] = str(rate_limit_info.get("remaining_hour", 0))
        response.headers["X-Response-Time"] = str(response_time)
        response.headers["X-Request-ID"] = rid

        return response
    finally:
        observability.reset_request_id(rid_token)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global API Error on {request.url.path}: {str(exc)}", exc_info=True)
    if healer:
        healer.log_error("global_api_exception", str(exc), "high")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


brain = IgrisBrain()
sys_ctrl = SystemController()

# Align app-level quantum_brain with brain instance when both exist
if quantum_brain is None and getattr(brain, "quantum_brain", None) is not None:
    quantum_brain = brain.quantum_brain


@app.get("/health")
async def root_health():
    """Liveness probe for load balancers and quick sanity checks."""
    return {
        "status": "ok",
        "service": "sikander-os-api",
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "ui": "hud-chat",
    }


@app.get("/system/feature-audit")
async def feature_audit():
    """Truth table of major backend capabilities: working / partial / missing."""
    return _feature_audit()


@app.get("/auth/status")
async def auth_status():
    """Expose whether token auth is enabled (for the frontend login gate)."""
    return api_auth.get_auth_status()


@app.post("/auth/verify")
async def auth_verify(request: Request):
    """Verify a token without revealing it. Returns 200 + valid flag."""
    if not api_auth.is_auth_enabled():
        return {"valid": True, "auth_enabled": False}
    ok = api_auth.verify_request(request)
    return JSONResponse(
        status_code=200 if ok else 401,
        content={"valid": ok, "auth_enabled": True},
    )


def _known_folder_from_text(text: str) -> str | None:
    """Resolve simple natural-language folder open requests to local paths."""
    q = text.lower().strip()
    home = os.path.expanduser("~")
    known = {
        "desktop": os.path.join(home, "Desktop"),
        "downloads": os.path.join(home, "Downloads"),
        "download": os.path.join(home, "Downloads"),
        "documents": os.path.join(home, "Documents"),
        "document": os.path.join(home, "Documents"),
        "pictures": os.path.join(home, "Pictures"),
        "images": os.path.join(home, "Pictures"),
        "videos": os.path.join(home, "Videos"),
        "music": os.path.join(home, "Music"),
        "project": os.getcwd(),
        "workspace": os.path.abspath(os.path.join(os.getcwd(), "..")),
        "repo": os.path.abspath(os.path.join(os.getcwd(), "..")),
    }
    for key, path in known.items():
        if key in q:
            return path
    if "file explorer" in q or q == "explorer" or "explorer open" in q:
        return home
    if "this pc" in q or "my computer" in q or "mera pc" in q or "mera computer" in q:
        return os.environ.get("SystemDrive", "C:") + "\\"
    if "my pc" in q:
        return os.environ.get("SystemDrive", "C:") + "\\"

    # Allow explicit existing paths, e.g. "open C:\Users\AABI\Desktop".
    marker_words = ("open", "khol", "kholo", "folder", "path")
    if any(w in q for w in marker_words):
        for token in text.replace('"', "").split():
            candidate = os.path.expanduser(token)
            if os.path.exists(candidate):
                return candidate
    return None


def _open_local_path(path: str) -> dict:
    """Open a local file/folder using the OS shell."""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        # Non-Windows fallback; best-effort for Linux/macOS dev.
        import subprocess
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([opener, path])
    return {"status": "opened", "path": path}


def _known_app_from_text(text: str) -> tuple[str, str] | None:
    """Resolve natural-language app launch requests."""
    q = text.lower().strip()
    aliases = {
        "chrome": ("Chrome", "chrome"),
        "google chrome": ("Chrome", "chrome"),
        "browser": ("Default browser", "__default_browser__"),
        "edge": ("Microsoft Edge", "msedge"),
        "microsoft edge": ("Microsoft Edge", "msedge"),
        "notepad": ("Notepad", "notepad"),
        "calculator": ("Calculator", "calc"),
        "calc": ("Calculator", "calc"),
        "cmd": ("Command Prompt", "cmd"),
        "command prompt": ("Command Prompt", "cmd"),
        "terminal": ("Terminal", "wt"),
        "powershell": ("PowerShell", "powershell"),
        "vscode": ("VS Code", "code"),
        "vs code": ("VS Code", "code"),
        "explorer": ("File Explorer", "explorer"),
    }
    wants_open = any(w in q for w in ("open", "launch", "khol", "kholo", "chala", "start"))
    if not wants_open:
        return None
    for key, value in aliases.items():
        if key in q:
            return value
    return None


def _open_local_app(display_name: str, command: str) -> dict:
    """Open a local desktop app using the OS shell."""
    if command == "__default_browser__":
        import webbrowser
        webbrowser.open("https://www.google.com")
    elif os.name == "nt":
        import subprocess
        subprocess.Popen(f'start "" {command}', shell=True)
    else:
        import subprocess
        subprocess.Popen([command])
    return {"status": "opened", "app": display_name, "command": command}


def _capabilities_text() -> str:
    return (
        "I can execute real local actions now: open folders/apps, list files, "
        "read system status, scan network, OCR screen, organize folders, search web, "
        "switch/list models, and report agents/daemons. Some advanced routes are still "
        "simulation/scaffold, but these actions are wired."
    )


def _agent_status_text() -> str:
    daemons = []
    for name in (
        "blood_ward", "dominion", "phantom_recon", "necromancy", "soul_link",
        "dream_space", "singularity", "akashic", "omnipresence", "chronos",
        "legion", "gods_eye",
    ):
        attr = f"{name}_active"
        if hasattr(brain, attr):
            daemons.append({"name": name, "active": bool(getattr(brain, attr))})
    shadow = getattr(brain, "shadow_army", []) or []
    active_count = sum(1 for d in daemons if d["active"])
    return (
        f"Agents/daemons found: {len(daemons)} daemon flags, {active_count} active, "
        f"{len(shadow)} shadow agents.\n"
        + "\n".join(f"- {d['name']}: {'active' if d['active'] else 'idle'}" for d in daemons)
    )


def _feature_audit() -> dict:
    """Runtime truth table for the major backend claims."""
    optional = {
        "neural_memory": neural_memory is not None,
        "self_healing": healer is not None,
        "emotional_ai": getattr(brain, "emotional_ai", None) is not None if "brain" in globals() else False,
        "predictive_engine": getattr(brain, "predictor", None) is not None if "brain" in globals() else False,
        "oracle": getattr(brain, "oracle", None) is not None if "brain" in globals() else False,
        "knowledge_graph": getattr(brain, "knowledge_graph", None) is not None if "brain" in globals() else False,
        "evolution_engine": getattr(brain, "evolution_engine", None) is not None if "brain" in globals() else False,
        "core_brain": getattr(brain, "core_brain", None) is not None if "brain" in globals() else False,
    }

    daemons = []
    if "daemon_master" in globals() and daemon_master:
        try:
            status = daemon_master.get_status()
            daemon_items = status.get("daemons", status) if isinstance(status, dict) else {}
            daemons = list(daemon_items.keys()) if isinstance(daemon_items, dict) else []
        except Exception:
            daemons = []

    return {
        "working": [
            "chat_http",
            "chat_stream_full_brain",
            "local_folder_open",
            "local_app_open",
            "system_status",
            "file_list",
            "web_search_browser",
            "model_catalog",
            "provider_keys",
            "tools_calculate_python_files",
        ],
        "partial": [
            "agents_daemons",
            "neural_memory_recall",
            "knowledge_graph_ingest",
            "economy_paper_mode",
            "vision_if_optional_deps_installed",
            "self_healing_capture_snapshot",
        ],
        "not_real_or_missing": [
            "model_weight_training",
            "self_evolution_engine" if not optional["evolution_engine"] else "",
            "offline_core_brain" if not optional["core_brain"] else "",
            "real_iot_control",
            "real_overclocking",
            "god_mode_as_real_world_power",
        ],
        "runtime": {
            "optional_modules": optional,
            "daemon_count": len(daemons),
            "daemons": daemons,
        },
    }


def _feature_audit_text() -> str:
    audit = _feature_audit()
    lines = ["Backend honest audit:"]
    lines.append("\nWorking:")
    lines.extend(f"- {x}" for x in audit["working"] if x)
    lines.append("\nPartial:")
    lines.extend(f"- {x}" for x in audit["partial"] if x)
    lines.append("\nNot real / missing:")
    lines.extend(f"- {x}" for x in audit["not_real_or_missing"] if x)
    lines.append("\nRuntime:")
    lines.append(f"- daemon_count: {audit['runtime']['daemon_count']}")
    for k, v in audit["runtime"]["optional_modules"].items():
        lines.append(f"- {k}: {'loaded' if v else 'missing'}")
    return "\n".join(lines)


def _reply_action(text: str, action: str, extra: dict | None = None) -> dict:
    data = {
        "text": text,
        "response": text,
        "agent": "igris",
        "action": action,
    }
    if extra:
        data.update(extra)
    return data


def _maybe_handle_local_action(text: str) -> dict | None:
    """Handle direct OS actions before sending the prompt to the LLM."""
    q = text.lower()

    # Capability / status questions should be answered honestly from wired actions.
    if any(p in q for p in ("kya kar sak", "what can you do", "features", "capabilities")):
        return _reply_action(_capabilities_text(), "capabilities")

    if any(p in q for p in ("kitna agent", "kitne agent", "agents hai", "daemon", "agent count")):
        return _reply_action(_agent_status_text(), "agent_status")

    if any(p in q for p in ("backend audit", "feature audit", "backend status", "kya real", "kya kaam")):
        return _reply_action(_feature_audit_text(), "feature_audit", {"audit": _feature_audit()})

    # Live system actions.
    if any(p in q for p in ("system status", "system info", "pc status", "computer status", "cpu", "ram")):
        result = sys_ctrl.get_system_info()
        return _reply_action(str(result), "system_info", {"result": result})

    if "network scan" in q or "scan network" in q or "network devices" in q:
        result = sys_ctrl.scan_network()
        return _reply_action(str(result or "No network data returned."), "network_scan", {"result": result})

    if any(p in q for p in ("read screen", "screen read", "ocr screen", "screen ka text", "screen par kya")):
        result = sys_ctrl.read_screen()
        return _reply_action(str(result), "screen_ocr", {"result": result})

    if "organize" in q or "folder sort" in q or "files sort" in q:
        path = _known_folder_from_text(text) or os.path.expanduser("~/Downloads")
        ok, result = sys_ctrl.organize_directory(path)
        return _reply_action(str(result), "organize_directory", {"ok": ok, "path": path, "result": result})

    if "list files" in q or "files dikhao" in q or "folder list" in q:
        path = _known_folder_from_text(text) or os.path.expanduser("~")
        result = sys_ctrl.list_directory(path)
        return _reply_action(str(result), "list_directory", {"path": path, "result": result})

    if "google search" in q or "web search" in q or q.startswith("search "):
        query = (
            text.lower()
            .replace("google search", "")
            .replace("web search", "")
            .replace("search", "", 1)
            .strip()
        )
        if query:
            ok = sys_ctrl.search_browser(query)
            return _reply_action(f"Searching web for: {query}", "web_search", {"ok": ok, "query": query})

    if "open app" in q or "app open" in q or "launch app" in q:
        app_name = (
            text.lower()
            .replace("open app", "")
            .replace("app open", "")
            .replace("launch app", "")
            .replace("karo", "")
            .strip()
        )
        if app_name:
            ok = sys_ctrl.open_app(app_name)
            return _reply_action(
                f"{'Opened' if ok else 'Could not open'} app: {app_name}",
                "open_app",
                {"ok": ok, "app": app_name},
            )

    app = _known_app_from_text(text)
    if app:
        opened = _open_local_app(app[0], app[1])
        return _reply_action(
            f"Opened: {opened['app']}",
            "open_app",
            opened,
        )

    if "close app" in q or "app close" in q:
        app_name = (
            text.lower()
            .replace("close app", "")
            .replace("app close", "")
            .replace("karo", "")
            .strip()
        )
        if app_name:
            ok = sys_ctrl.close_app(app_name)
            return _reply_action(
                f"{'Closed' if ok else 'Could not close'} app: {app_name}",
                "close_app",
                {"ok": ok, "app": app_name},
            )

    wants_open = any(w in q for w in (
        "open", "khol", "kholo", "folder", "explorer", "desktop",
        "downloads", "documents", "pictures", "this pc", "my pc", "mera pc",
    ))
    if not wants_open:
        return None

    # Windows: "This PC" / "My PC" is a virtual folder; shell open works better than C:\.
    if os.name == "nt" and any(
        p in q for p in ("this pc", "my computer", "my pc", "mera pc", "mera computer")
    ):
        import subprocess
        subprocess.Popen("explorer shell:MyComputerFolder", shell=True)
        return {
            "status": "opened",
            "path": "shell:MyComputerFolder",
            "text": "Opened: This PC (File Explorer)",
            "response": "Opened: This PC (File Explorer)",
            "agent": "igris",
            "action": "open_path",
        }

    path = _known_folder_from_text(text)
    if not path:
        return None

    opened = _open_local_path(path)
    return {
        **opened,
        "text": f"Opened: {opened['path']}",
        "response": f"Opened: {opened['path']}",
        "agent": "igris",
        "action": "open_path",
    }


@app.post("/chat")
async def chat_endpoint(payload: dict):
    """HTTP chat for the Sikander OS frontend (mirrors WebSocket /ws/chat behaviour)."""
    text = (payload or {}).get("message") or (payload or {}).get("text") or ""
    text = str(text).strip()
    if not text:
        return JSONResponse(status_code=400, content={"error": "message or text required"})
    try:
        app_metrics.inc("chat_requests")
        local_action = _maybe_handle_local_action(text)
        if local_action:
            app_metrics.inc("chat_ok")
            return local_action
        result = await brain.process_command(text, (payload or {}).get("agent", "igris"))
        app_metrics.inc("chat_ok")
        return {
            "text": result.get("text", ""),
            "response": result.get("text", ""),
            "agent": result.get("agent", "igris"),
            "emotion": result.get("emotion"),
            "audio_sync": result.get("audio_sync"),
        }
    except Exception as ex:
        logger.exception("chat_endpoint failed")
        app_metrics.inc("chat_err")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Chat execution failed",
                "code": "CHAT_EXECUTION_FAILED",
                "request_id": observability.get_request_id(),
            },
        )


@app.post("/chat/stream")
async def chat_stream_endpoint(payload: dict):
    """SSE reply stream. Uses full brain command path so tools/actions can execute."""
    text = (payload or {}).get("message") or (payload or {}).get("text") or ""
    text = str(text).strip()
    if not text:
        return JSONResponse(status_code=400, content={"error": "message or text required"})
    app_metrics.inc("chat_stream_requests")

    async def event_gen():
        buf: list[str] = []
        try:
            local_action = _maybe_handle_local_action(text)
            if local_action:
                reply = local_action["response"]
                yield f"data: {json.dumps({'chunk': reply})}\n\n"
                yield f"data: {json.dumps({'done': True, 'text': reply})}\n\n"
                app_metrics.inc("chat_stream_ok")
                return
            # Important: use the full command path, not the lightweight toolless
            # LLM token stream. This keeps memory, tools, local actions, and
            # self-learning side effects active for the frontend chat.
            result = await brain.process_command(text, (payload or {}).get("agent", "igris"))
            full_text = str(result.get("text", "") or result.get("response", ""))
            for idx in range(0, len(full_text), 80):
                chunk = full_text[idx:idx + 80]
                buf.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.01)
            full = "".join(buf)
            yield f"data: {json.dumps({'done': True, 'text': full})}\n\n"
            app_metrics.inc("chat_stream_ok")
        except Exception as ex:
            logger.exception("chat_stream failed")
            yield f"data: {json.dumps({'error': 'stream_failed', 'code': 'CHAT_STREAM_FAILED', 'done': True})}\n\n"
            app_metrics.inc("chat_stream_err")

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/actions/pending")
async def get_pending_action():
    pending = brain.get_pending_action() if hasattr(brain, "get_pending_action") else None
    return {
        "has_pending_action": bool(pending),
        "pending_action": pending,
        "request_id": observability.get_request_id(),
    }


@app.post("/actions/pending/approve")
async def approve_pending_action():
    result = brain.approve_pending_action() if hasattr(brain, "approve_pending_action") else {"ok": False, "error": "Action manager unavailable"}
    if result.get("ok"):
        app_metrics.inc("action_approve_ok")
    else:
        app_metrics.inc("action_approve_err")
    return {
        **result,
        "request_id": observability.get_request_id(),
    }


@app.post("/actions/pending/cancel")
async def cancel_pending_action(payload: dict | None = None):
    reason = str((payload or {}).get("reason") or "cancelled_via_api")
    ok = brain.clear_pending_action(reason=reason) if hasattr(brain, "clear_pending_action") else False
    if ok:
        app_metrics.inc("action_cancel_ok")
    else:
        app_metrics.inc("action_cancel_err")
    return {
        "ok": ok,
        "reason": reason,
        "request_id": observability.get_request_id(),
    }


@app.get("/actions/audit")
async def action_audit(limit: int = 20):
    data = brain.get_action_audit(limit=limit) if hasattr(brain, "get_action_audit") else []
    return {
        "count": len(data),
        "items": data,
        "request_id": observability.get_request_id(),
    }


@app.get("/observability/snapshot")
async def observability_snapshot():
    """Counters + job queue depth (protect with IGRIS_API_TOKEN in production)."""
    return {
        "request_id": observability.get_request_id(),
        "metrics": app_metrics.snapshot(),
        "job_queue_depth": job_queue_depth(),
    }


# Initialize health checks
health_check.register_component("database", "SQLite Database")
health_check.register_component("api", "FastAPI Server")
health_check.register_component("ai_core", "Igris AI Core")

# Set shared dependencies and include API routes
wire_shared_dependencies(brain, sys_ctrl)
register_all_routers(app)

# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup"""
    logger.info("Igris AI Assistant Starting Up...")
    api_auth.validate_auth_configuration()
    
    # Initialize database
    logger.info("Database initialized")
    
    # Initialize health checks
    health_check.update_component_status("database", "healthy", 10)
    health_check.update_component_status("api", "healthy", 5)
    health_check.update_component_status("ai_core", "healthy", 20)
    health_check.register_component("daemons", "Daemon Systems")
    
    # Start all 13 daemons
    logger.info("Initializing 13 Daemon Systems...")
    daemon_results = await daemon_master.start_all()
    health_check.update_component_status("daemons", "healthy", 30)
    logger.info(f"Daemons started: {daemon_results}")
    
    # Start task orchestrator
    asyncio.create_task(task_orchestrator.start_orchestration())
    logger.info("Task orchestrator started")

    start_job_worker()
    logger.info("Async job queue worker ready")
    
    # ── NEW: Start Scheduler ─────────────────────────────────────────────
    try:
        from app.core.scheduler import get_scheduler
        scheduler = get_scheduler()
        await scheduler.start()
        health_check.register_component("scheduler", "Job Scheduler")
        health_check.update_component_status("scheduler", "healthy", 5)
        logger.info("Scheduler started ⏰")
    except Exception as _e:
        logger.warning(f"Scheduler failed to start: {_e}")
    
    # ── NEW: Load Plugins ────────────────────────────────────────────────
    try:
        from app.core.plugin_loader import get_plugin_loader
        plugin_loader = get_plugin_loader()
        plugin_results = plugin_loader.load_all()
        plugin_loader.fire_startup()
        health_check.register_component("plugins", "Plugin System")
        health_check.update_component_status("plugins", "healthy", 5)
        logger.info(f"Plugins loaded: {plugin_results} 🔌")
    except Exception as _e:
        logger.warning(f"Plugin loader failed: {_e}")
    
    # ── NEW: Wire WebSocket Hub to brain ──────────────────────────────────
    ws_hub.set_brain(brain)
    logger.info("WebSocket Hub connected to Brain 🔴")
    
    # ── NEW: Register Self-Healer health checks ──────────────────────────
    if healer:
        health_check.register_component("self_healer", "Self-Healing Engine")
        health_check.update_component_status("self_healer", "healthy", 5)
    
    logger.info("━━━ Igris OS — ALL SYSTEMS ONLINE ━━━ 🚀⚔️")

@app.on_event("shutdown")
async def shutdown_event():
    """Graceful shutdown"""
    logger.info("Igris shutting down...")
    try:
        brain.shutdown()
    except Exception as e:
        logger.error(f"Error shutting down brain: {e}")
    try:
        from app.core.scheduler import get_scheduler
        await get_scheduler().stop()
    except Exception:
        pass
    try:
        from app.core.plugin_loader import get_plugin_loader
        get_plugin_loader().fire_shutdown()
    except Exception:
        pass
    logger.info("Igris shut down. Farewell, My Liege. ⚔️")

@app.get("/system/stats")
async def get_system_stats():
    return {
        "cpu": psutil.cpu_percent(),
        "memory": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage(_disk_usage_root()).percent
    }

# ==================== ADVANCED MONITORING ENDPOINTS ====================

@app.get("/monitor/stats")
async def get_monitoring_stats():
    """Get comprehensive monitoring statistics"""
    return advanced_monitor.get_monitoring_stats()

@app.get("/monitor/operations")
async def get_operations_metrics():
    """Get operation-level metrics"""
    return advanced_monitor.metrics_collector.get_all_stats()

@app.get("/monitor/error-history")
async def get_error_history(limit: int = 50):
    """Get error history"""
    return {
        "errors": error_handler.get_error_history(limit),
        "stats": error_handler.get_stats()
    }

@app.get("/monitor/health-detailed")
async def get_detailed_health():
    """Get detailed health information"""
    return {
        "system": {
            "cpu": psutil.cpu_percent(),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage(_disk_usage_root()).percent
        },
        "monitoring": advanced_monitor.get_monitoring_stats(),
        "error_recovery": error_handler.get_stats()
    }

# ==================== DAEMON SYSTEM ENDPOINTS ====================

@app.get("/daemons/status")
async def get_daemons_status():
    """Get status of all 13 daemons"""
    return daemon_master.get_status()

@app.get("/daemons/{daemon_name}/status")
async def get_daemon_status(daemon_name: str):
    """Get specific daemon status"""
    daemon = daemon_master.get_daemon(daemon_name)
    if daemon:
        return daemon.get_status()
    return {"error": "Daemon not found"}

@app.post("/daemons/{daemon_name}/command")
async def send_daemon_command(daemon_name: str, command: DaemonCommandRequest):
    """Send command to a daemon"""
    # Accept both params (backend contract) and args (older frontend contract).
    params = command.params or command.args or {}
    result = await daemon_master.send_command(daemon_name, command.command, params)
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/daemons/event/emit")
async def emit_daemon_event(payload: DaemonEventRequest):
    """Queue an internal daemon bus event for orchestration."""
    result = await daemon_master.emit_event(payload.target, payload.command, payload.params)
    return result

@app.post("/daemons/start")
async def start_all_daemons():
    """Start all daemons"""
    return await daemon_master.start_all()

@app.post("/daemons/stop")
async def stop_all_daemons():
    """Stop all daemons"""
    return await daemon_master.stop_all()

@app.post("/daemons/forge")
async def forge_dynamic_daemon(forge_data: ForgeDaemonRequest, request: Request):
    """GOD LEVEL PHASE 2: Dynamically forge a new Python daemon at runtime using Shadow Forge generated code."""
    _enforce_sensitive_route_auth(request)
    result = await daemon_master.create_dynamic_daemon(
        class_name=forge_data.class_name,
        daemon_code=forge_data.code
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("error", "Forge failed"))
    return result

# Daemon-specific endpoints
@app.get("/daemons/blood_ward/threats")
async def get_threats():
    """Get security threats detected by Blood Ward"""
    daemon = daemon_master.get_daemon("blood_ward")
    if daemon and hasattr(daemon, 'get_threats'):
        return {"threats": daemon.get_threats()}
    return {"error": "Blood Ward daemon not available"}

@app.post("/daemons/blood_ward/block_ip")
async def block_ip(ip: BlockIPRequest):
    """Block an IP address"""
    daemon = daemon_master.get_daemon("blood_ward")
    if daemon and hasattr(daemon, 'add_blocked_ip'):
        result = await daemon.add_blocked_ip(ip.ip)
        return result
    return {"error": "Blood Ward daemon not available"}

@app.get("/daemons/dominion/system_info")
async def get_dominion_system_info():
    """Get system info from Dominion daemon"""
    daemon = daemon_master.get_daemon("dominion")
    if daemon and hasattr(daemon, 'get_system_info'):
        return daemon.get_system_info()
    return {"error": "Dominion daemon not available"}

@app.get("/daemons/phantom_recon/network_info")
async def get_network_info():
    """Get network info from Phantom Recon"""
    daemon = daemon_master.get_daemon("phantom_recon")
    if daemon and hasattr(daemon, 'get_network_info'):
        return daemon.get_network_info()
    return {"error": "Phantom Recon daemon not available"}

@app.post("/daemons/phantom_recon/scan_port")
async def scan_port(scan_data: PortScanRequest):
    """Scan a port using Phantom Recon"""
    daemon = daemon_master.get_daemon("phantom_recon")
    if daemon and hasattr(daemon, 'scan_port'):
        result = await daemon.scan_port(scan_data.host, scan_data.port)
        return result
    return {"error": "Phantom Recon daemon not available"}

@app.get("/daemons/crimson_ledger/portfolio")
async def get_portfolio():
    """Get portfolio from Crimson Ledger"""
    daemon = daemon_master.get_daemon("crimson_ledger")
    if daemon and hasattr(daemon, 'get_portfolio'):
        return daemon.get_portfolio()
    return {"error": "Crimson Ledger daemon not available"}

@app.post("/daemons/storm_caller/schedule")
async def schedule_task(task_data: ScheduleTaskRequest, request: Request):
    """Schedule a task with Storm Caller"""
    _enforce_sensitive_route_auth(request)
    daemon = daemon_master.get_daemon("storm_caller")
    if daemon and hasattr(daemon, 'schedule_task'):
        result = daemon.schedule_task(
            task_data.name,
            task_data.action,
            task_data.params,
            task_data.schedule,
            task_data.recurring
        )
        return result
    return {"error": "Storm Caller daemon not available"}

@app.get("/daemons/void_walker/search")
async def search_files(query: str, directory: str = ""):
    """Search files with Void Walker"""
    daemon = daemon_master.get_daemon("void_walker")
    if daemon and hasattr(daemon, 'search_files'):
        default_root = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ("C:\\" if os.name == "nt" else "/")
        results = await daemon.search_files(directory or default_root, query)
        return {"results": results}
    return {"error": "Void Walker daemon not available"}

@app.post("/daemons/aether_eye/ocr")
async def perform_ocr(ocr_data: OCRRequest):
    """Perform OCR with Aether Eye"""
    daemon = daemon_master.get_daemon("aether_eye")
    if daemon and hasattr(daemon, 'queue_vision_task'):
        daemon.queue_vision_task(ocr_data.image_path, 'ocr')
        return {"status": "queued"}
    return {"error": "Aether Eye daemon not available"}

@app.post("/daemons/whisper_wind/speak")
async def text_to_speech(speak_data: SpeakRequest):
    """Text to speech with Whisper Wind"""
    daemon = daemon_master.get_daemon("whisper_wind")
    if daemon and hasattr(daemon, 'speak'):
        result = daemon.speak(speak_data.text)
        return result
    return {"error": "Whisper Wind daemon not available"}

@app.get("/daemons/iron_crown/hardware")
async def get_hardware_info():
    """Get hardware info from Iron Crown"""
    daemon = daemon_master.get_daemon("iron_crown")
    if daemon and hasattr(daemon, 'get_hardware_info'):
        return daemon.get_hardware_info()
    return {"error": "Iron Crown daemon not available"}

@app.get("/daemons/chronos/uptime")
async def get_system_uptime():
    """Get system uptime from Chronos"""
    daemon = daemon_master.get_daemon("chronos")
    if daemon and hasattr(daemon, 'get_system_uptime'):
        return daemon.get_system_uptime()
    return {"error": "Chronos daemon not available"}

@app.post("/daemons/chronos/predict")
async def predict_trend(predict_data: dict):
    """Predict trend with Chronos"""
    daemon = daemon_master.get_daemon("chronos")
    if daemon and hasattr(daemon, 'predict_trend'):
        result = await daemon.predict_trend(predict_data.get('data'), predict_data.get('periods', 5))
        return result
    return {"error": "Chronos daemon not available"}

@app.post("/daemons/chronos/snapshot")
async def take_system_snapshot(body: dict = {}):
    """Take a real system snapshot with Chronos"""
    daemon = daemon_master.get_daemon("chronos")
    if daemon and hasattr(daemon, 'take_snapshot'):
        return await daemon.take_snapshot(reason=body.get("reason", "manual"))
    return {"error": "Chronos daemon not available"}

@app.get("/daemons/chronos/snapshots")
async def list_snapshots():
    """List all saved snapshots"""
    daemon = daemon_master.get_daemon("chronos")
    if daemon and hasattr(daemon, 'list_snapshots'):
        return {"snapshots": daemon.list_snapshots()}
    return {"error": "Chronos daemon not available"}

@app.get("/daemons/chronos/forecast")
async def get_resource_forecast(resource: str = "cpu", periods: int = 10):
    """Get CPU/memory resource forecast from Chronos historical data"""
    daemon = daemon_master.get_daemon("chronos")
    if daemon and hasattr(daemon, 'get_resource_forecast'):
        return daemon.get_resource_forecast(resource=resource, periods=periods)
    return {"error": "Chronos daemon not available"}

# ── Void Walker Extended Endpoints ──────────────────────────────────────────

class VoidWalkerOpRequest(BaseModel):
    op_type: str = Field(..., description="copy | move | delete | compress")
    src: str = Field(..., min_length=1)
    dst: str = ""
    files: list = []

@app.get("/daemons/void_walker/tree")
async def get_directory_tree(directory: str, depth: int = 2):
    """Get directory tree structure from Void Walker"""
    daemon = daemon_master.get_daemon("void_walker")
    if daemon and hasattr(daemon, 'get_directory_tree'):
        return await daemon.get_directory_tree(directory, depth)
    return {"error": "Void Walker daemon not available"}

@app.post("/daemons/void_walker/operation")
async def queue_file_operation(op: VoidWalkerOpRequest):
    """Queue a file operation (copy/move/delete/compress) on Void Walker"""
    daemon = daemon_master.get_daemon("void_walker")
    if daemon and hasattr(daemon, 'queue_operation'):
        return daemon.queue_operation(op.op_type, op.src, op.dst, op.files or None)
    return {"error": "Void Walker daemon not available"}

@app.get("/daemons/void_walker/operation_log")
async def get_file_operation_log(limit: int = 50):
    """Get Void Walker file operation history"""
    daemon = daemon_master.get_daemon("void_walker")
    if daemon and hasattr(daemon, 'get_operation_log'):
        return {"log": daemon.get_operation_log(limit)}
    return {"error": "Void Walker daemon not available"}

# ── Storm Caller Extended Endpoints ─────────────────────────────────────────

@app.get("/daemons/storm_caller/tasks")
async def get_scheduled_tasks():
    """Get all scheduled Storm Caller tasks"""
    daemon = daemon_master.get_daemon("storm_caller")
    if daemon and hasattr(daemon, 'get_tasks'):
        return {"tasks": daemon.get_tasks()}
    return {"error": "Storm Caller daemon not available"}

@app.delete("/daemons/storm_caller/tasks/{task_id}")
async def cancel_scheduled_task(task_id: str):
    """Cancel a scheduled Storm Caller task by ID"""
    daemon = daemon_master.get_daemon("storm_caller")
    if daemon and hasattr(daemon, 'cancel_task'):
        return daemon.cancel_task(task_id)
    return {"error": "Storm Caller daemon not available"}

# ── Data Drake Extended Endpoints ────────────────────────────────────────────

@app.post("/daemons/data_drake/analyze_csv")
async def analyze_csv_file(body: dict):
    """Analyze a CSV file with Data Drake (full stats per column)"""
    daemon = daemon_master.get_daemon("data_drake")
    if daemon and hasattr(daemon, 'analyze_csv'):
        return await daemon.analyze_csv(body.get("file_path", ""), body.get("columns"))
    return {"error": "Data Drake daemon not available"}

@app.post("/daemons/data_drake/analyze_json")
async def analyze_json_file(body: dict):
    """Analyze a JSON file with Data Drake"""
    daemon = daemon_master.get_daemon("data_drake")
    if daemon and hasattr(daemon, 'analyze_json'):
        return await daemon.analyze_json(body.get("file_path", ""))
    return {"error": "Data Drake daemon not available"}

@app.get("/daemons/data_drake/datasets")
async def list_datasets():
    """List loaded datasets in Data Drake"""
    daemon = daemon_master.get_daemon("data_drake")
    if daemon and hasattr(daemon, 'get_dataset_names'):
        return {"datasets": daemon.get_dataset_names()}
    return {"error": "Data Drake daemon not available"}

# ── Iron Crown Extended Endpoints ────────────────────────────────────────────

@app.get("/daemons/iron_crown/processes")
async def get_process_list(sort_by: str = "cpu", limit: int = 20):
    """Get top processes by CPU or memory usage from Iron Crown"""
    daemon = daemon_master.get_daemon("iron_crown")
    if daemon and hasattr(daemon, 'get_process_list'):
        return {"processes": await daemon.get_process_list(sort_by=sort_by, limit=limit)}
    return {"error": "Iron Crown daemon not available"}

@app.post("/daemons/iron_crown/control")
async def control_hardware_device(body: dict):
    """Control hardware device via Iron Crown (display/audio/power)"""
    daemon = daemon_master.get_daemon("iron_crown")
    if daemon and hasattr(daemon, 'control_device'):
        return await daemon.control_device(
            body.get("device_type", ""),
            body.get("action", ""),
            body.get("params", {})
        )
    return {"error": "Iron Crown daemon not available"}

@app.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """Get a distributed trace"""
    trace = advanced_monitor.tracer.get_trace(trace_id)
    if not trace:
        return {"error": "Trace not found"}
    return advanced_monitor.tracer.get_trace_summary(trace_id)

# ==================== ERROR & RECOVERY ENDPOINTS ====================

@app.get("/errors/stats")
async def get_error_stats():
    """Get error statistics"""
    return error_handler.get_stats()

@app.get("/errors/circuit-breakers")
async def get_circuit_breakers():
    """Get circuit breaker states"""
    return {
        "circuit_breakers": {
            name: breaker.get_state()
            for name, breaker in error_handler.circuit_breakers.items()
        }
    }

# ==================== NEURAL MEMORY ENDPOINTS ====================

@app.get("/memory/stats")
async def get_memory_stats():
    """Get Neural Memory statistics"""
    if not neural_memory:
        return {"error": "Neural Memory not available"}
    return neural_memory.get_stats()

@app.post("/memory/remember")
async def store_memory(data: dict):
    """Store a new memory in the Vector DB"""
    if not neural_memory:
        return {"error": "Neural Memory not available"}
    rec = neural_memory.remember(
        content=data.get("content", ""),
        memory_type=data.get("memory_type", "semantic"),
        tags=data.get("tags", []),
        metadata=data.get("metadata", {}),
        importance=data.get("importance", 0.5),
    )
    return {"status": "stored", "id": rec.id, "type": rec.memory_type}

@app.get("/memory/recall")
async def recall_memory(query: str, top_k: int = 5, memory_type: str = None):
    """Semantic recall from Vector DB"""
    if not neural_memory:
        return {"error": "Neural Memory not available"}
    results = neural_memory.recall(query, top_k=top_k, memory_type=memory_type)
    return {
        "query": query,
        "results": [
            {"content": r.content, "similarity": round(s, 4),
             "type": r.memory_type, "importance": r.importance,
             "id": r.id, "tags": r.tags}
            for r, s in results
        ]
    }

@app.delete("/memory/{memory_id}")
async def delete_memory(memory_id: str):
    """Forget a specific memory"""
    if not neural_memory:
        return {"error": "Neural Memory not available"}
    ok = neural_memory.forget(memory_id)
    return {"success": ok}

@app.get("/memory/type/{memory_type}")
async def get_by_type(memory_type: str):
    """Get all memories of a specific type"""
    if not neural_memory:
        return {"error": "Neural Memory not available"}
    records = neural_memory.get_all_by_type(memory_type)
    return {
        "type": memory_type,
        "count": len(records),
        "memories": [{"id": r.id, "content": r.content[:200],
                      "importance": r.importance, "tags": r.tags} for r in records]
    }

@app.get("/memory/{memory_id}/links")
async def get_memory_links(memory_id: str):
    """Get associative links for a memory"""
    if not neural_memory:
        return {"error": "Neural Memory not available"}
    return {"links": neural_memory.get_linked_memories(memory_id)}

@app.post("/memory/link")
async def link_memories(data: dict):
    """Create an associative link between two memories"""
    if not neural_memory:
        return {"error": "Neural Memory not available"}
    neural_memory.link_memories(
        data.get("source_id"),
        data.get("target_id"),
        data.get("relation", "related"),
        data.get("strength", 1.0),
    )
    return {"status": "linked"}

@app.post("/memory/export")
async def export_memories(data: dict):
    """Export memories to JSON file"""
    if not neural_memory:
        return {"error": "Neural Memory not available"}
    path = data.get("path", "memory_export.json")
    msg = neural_memory.export_memories(path)
    return {"status": msg}

# ==================== SELF-HEALING ENGINE ====================

@app.get("/heal/stats")
async def get_heal_stats():
    """Get Self-Healing engine statistics"""
    if not healer:
        return {"error": "Self-Healing Engine not available"}
    return healer.get_stats()

@app.get("/heal/errors")
async def get_error_history(limit: int = 50):
    """Get captured error history"""
    if not healer:
        return {"error": "Self-Healing Engine not available"}
    return {"errors": healer.get_error_history(limit)}

@app.post("/heal/rollback")
async def rollback_file(data: dict):
    """Rollback a file to its last backup"""
    if not healer:
        return {"error": "Self-Healing Engine not available"}
    msg = healer.rollback(data.get("file_path", ""))
    return {"status": msg}

# ==================== EMOTIONAL INTELLIGENCE ====================

@app.get("/emotion/current")
async def get_current_emotion():
    """Get current detected emotion state"""
    if not emotional_ai:
        return {"error": "Emotional AI not available"}
    return emotional_ai.current_state.to_dict()

@app.get("/emotion/stats")
async def get_emotion_stats():
    """Get emotional analysis statistics"""
    if not emotional_ai:
        return {"error": "Emotional AI not available"}
    return emotional_ai.get_stats()

@app.post("/emotion/analyze")
async def analyze_emotion(data: dict):
    """Analyze emotion in a text"""
    if not emotional_ai:
        return {"error": "Emotional AI not available"}
    text = data.get("text", "")
    state = emotional_ai.analyze(text)
    return state.to_dict()

@app.get("/emotion/history")
async def get_emotion_history(limit: int = 50):
    """Get emotion history"""
    if not emotional_ai:
        return {"error": "Emotional AI not available"}
    return {"history": emotional_ai.get_emotion_history(limit)}

# ==================== PREDICTIVE ENGINE ====================

@app.get("/predict/stats")
async def get_predict_stats():
    """Get predictive engine statistics"""
    if not predictor:
        return {"error": "Predictive Engine not available"}
    return predictor.get_stats()

@app.get("/predict/patterns")
async def get_all_patterns():
    """Get all learned patterns"""
    if not predictor:
        return {"error": "Predictive Engine not available"}
    return {"patterns": predictor.get_all_patterns()}

@app.get("/predict/now")
async def get_current_predictions():
    """Get predictions relevant to current time"""
    if not predictor:
        return {"error": "Predictive Engine not available"}
    predictions = predictor.generate_predictions()
    return {"predictions": [p.to_dict() for p in predictions]}

@app.post("/predict/observe")
async def observe_command_endpoint(data: dict):
    """Feed a command to the predictive engine for learning"""
    if not predictor:
        return {"error": "Predictive Engine not available"}
    predictor.observe_command(data.get("command", ""), data.get("metadata", {}))
    return {"status": "observed"}

@app.delete("/predict/patterns/{pattern_id}")
async def delete_pattern(pattern_id: str):
    """Delete a learned pattern"""
    if not predictor:
        return {"error": "Predictive Engine not available"}
    ok = predictor.delete_pattern(pattern_id)
    return {"deleted": ok}

# ==================== QUANTUM VAULT ====================

@app.get("/vault/stats")
async def get_vault_stats():
    """Get Quantum Vault status"""
    if not vault:
        return {"error": "Quantum Vault not available"}
    return vault.get_stats()

@app.post("/vault/initialize")
async def initialize_vault(data: dict):
    """Initialize a new vault"""
    if not vault:
        return {"error": "Quantum Vault not available"}
    msg = vault.initialize(data.get("password", ""))
    return {"status": msg}

@app.post("/vault/unlock")
async def unlock_vault(data: dict):
    """Unlock the vault"""
    if not vault:
        return {"error": "Quantum Vault not available"}
    success = vault.unlock(data.get("password", ""))
    return {"success": success}

@app.post("/vault/lock")
async def lock_vault():
    """Lock the vault"""
    if not vault:
        return {"error": "Quantum Vault not available"}
    return {"status": vault.lock()}

@app.post("/vault/store")
async def store_secret(data: dict):
    """Store a secret in the vault"""
    if not vault:
        return {"error": "Quantum Vault not available"}
    try:
        entry_id = vault.store(
            label=data.get("label", ""),
            secret=data.get("secret", ""),
            category=data.get("category", "note"),
            tags=data.get("tags", []),
        )
        return {"status": "stored", "entry_id": entry_id}
    except PermissionError:
        return {"error": "Vault is locked"}

@app.get("/vault/list")
async def list_vault_entries():
    """List all vault entries (metadata only)"""
    if not vault:
        return {"error": "Quantum Vault not available"}
    try:
        return {"entries": vault.list_entries()}
    except PermissionError:
        return {"error": "Vault is locked"}

@app.get("/vault/retrieve/{entry_id}")
async def retrieve_secret(entry_id: str):
    """Retrieve a secret by ID"""
    if not vault:
        return {"error": "Quantum Vault not available"}
    try:
        secret = vault.retrieve(entry_id)
        if secret is None:
            return {"error": "Entry not found or tampered"}
        return {"secret": secret}
    except PermissionError:
        return {"error": "Vault is locked"}

@app.delete("/vault/{entry_id}")
async def delete_vault_entry(entry_id: str):
    """Delete a vault entry"""
    if not vault:
        return {"error": "Quantum Vault not available"}
    try:
        ok = vault.delete(entry_id)
        return {"deleted": ok}
    except PermissionError:
        return {"error": "Vault is locked"}

@app.get("/vault/audit")
async def get_vault_audit(limit: int = 50):
    """Get vault audit log"""
    if not vault:
        return {"error": "Quantum Vault not available"}
    return {"log": vault.get_audit_log(limit)}

# ==================== PHASE 5: GOD-TIER API ROUTES ====================

# ─── Digital Genome ───────────────────────────────────────────────────────────
@app.get("/genome/stats")
async def genome_stats():
    if not genome: return {"error": "Genome unavailable"}
    return genome.get_stats()

@app.get("/genome/export")
async def genome_export():
    if not genome: return {"error": "Genome unavailable"}
    return genome.export_genome()

@app.post("/genome/preset")
async def genome_preset(data: dict):
    if not genome: return {"error": "Genome unavailable"}
    msg = genome.apply_preset(data.get("preset", "warrior"), data.get("blend", 1.0))
    return {"status": msg}

@app.post("/genome/rollback")
async def genome_rollback(data: dict):
    if not genome: return {"error": "Genome unavailable"}
    msg = genome.rollback(int(data.get("version", 0)))
    return {"status": msg}

@app.get("/genome/versions")
async def genome_versions():
    if not genome: return {"error": "Genome unavailable"}
    return {"versions": genome.list_versions()}

# ─── Reality Anchor ───────────────────────────────────────────────────────────
@app.get("/anchor/stats")
async def anchor_stats():
    if not reality_anchor: return {"error": "Reality Anchor unavailable"}
    return reality_anchor.get_stats()

@app.get("/anchor/pending")
async def anchor_pending(priority: str = None):
    if not reality_anchor: return {"error": "Reality Anchor unavailable"}
    return {"anchors": reality_anchor.get_pending(priority)}

@app.get("/anchor/overdue")
async def anchor_overdue():
    if not reality_anchor: return {"error": "Reality Anchor unavailable"}
    return {"overdue": reality_anchor.get_overdue()}

@app.post("/anchor/complete/{anchor_id}")
async def anchor_complete(anchor_id: str, data: dict = {}):
    if not reality_anchor: return {"error": "Reality Anchor unavailable"}
    msg = reality_anchor.complete(anchor_id, data.get("note", ""))
    return {"status": msg}

@app.post("/anchor/extract")
async def anchor_extract(data: dict):
    if not reality_anchor: return {"error": "Reality Anchor unavailable"}
    new = reality_anchor.extract_and_store(data.get("text", ""))
    return {"extracted": [a.to_dict() for a in new]}

# ─── Cognitive Load ───────────────────────────────────────────────────────────
@app.get("/load/stats")
async def load_stats():
    if not cognitive_load: return {"error": "Cognitive Load unavailable"}
    return cognitive_load.get_stats()

@app.post("/load/analyze")
async def load_analyze(data: dict):
    if not cognitive_load: return {"error": "Cognitive Load unavailable"}
    score, state, style = cognitive_load.analyze(data.get("text", ""))
    return {"score": score, "state": state, "style": style}

# ─── Oracle Protocol ──────────────────────────────────────────────────────────
@app.get("/oracle/stats")
async def oracle_stats():
    if not oracle: return {"error": "Oracle unavailable"}
    return oracle.get_stats()

@app.get("/oracle/predictions")
async def oracle_predictions():
    if not oracle: return {"error": "Oracle unavailable"}
    return {"predictions": oracle.get_latest_predictions()}

@app.get("/oracle/alerts")
async def oracle_alerts_endpoint():
    if not oracle: return {"error": "Oracle unavailable"}
    return {"alerts": oracle.get_alerts()}

@app.get("/oracle/history")
async def oracle_history(limit: int = 50):
    if not oracle: return {"error": "Oracle unavailable"}
    return {"history": oracle.get_prophecy_log(limit)}

@app.post("/oracle/feed/price")
async def oracle_feed_price(data: dict):
    if not oracle: return {"error": "Oracle unavailable"}
    oracle.feed_price_series(data.get("symbol", "BTC"), data.get("prices", []))
    return {"status": "fed"}

# ─── Knowledge Graph ──────────────────────────────────────────────────────────
@app.get("/graph/stats")
async def graph_stats():
    if not knowledge_graph: return {"error": "Knowledge Graph unavailable"}
    return knowledge_graph.get_stats()

@app.get("/graph/export")
async def graph_export(max_nodes: int = 300):
    if not knowledge_graph: return {"error": "Knowledge Graph unavailable"}
    return knowledge_graph.export_for_viz(max_nodes)

@app.get("/graph/search")
async def graph_search(q: str, top_k: int = 10):
    if not knowledge_graph: return {"error": "Knowledge Graph unavailable"}
    return {"results": knowledge_graph.search(q, top_k)}

@app.get("/graph/top")
async def graph_top(k: int = 10):
    if not knowledge_graph: return {"error": "Knowledge Graph unavailable"}
    return {"nodes": knowledge_graph.most_important_nodes(k)}

@app.get("/graph/neighbours/{node_id}")
async def graph_neighbours(node_id: str, depth: int = 1):
    if not knowledge_graph: return {"error": "Knowledge Graph unavailable"}
    return {"neighbours": knowledge_graph.neighbours(node_id, depth)}

@app.get("/graph/path")
async def graph_path(from_id: str, to_id: str):
    if not knowledge_graph: return {"error": "Knowledge Graph unavailable"}
    return {"path": knowledge_graph.shortest_path(from_id, to_id)}

@app.post("/graph/ingest")
async def graph_ingest(data: dict):
    if not knowledge_graph: return {"error": "Knowledge Graph unavailable"}
    added = knowledge_graph.ingest_text(data.get("text", ""), data.get("source", "api"))
    return {"nodes_added": added}

# ─── Parallel Universe (Monte Carlo) ──────────────────────────────────────────
@app.post("/simulate")
async def simulate_action(data: dict):
    if not parallel_universe: return {"error": "Parallel Universe unavailable"}
    result = parallel_universe.simulate(
        action=data.get("action", ""),
        model=data.get("model", "generic"),
        params=data.get("params", {}),
        trials=int(data.get("trials", 1000)),
    )
    return result.to_dict()

@app.post("/simulate/should-i")
async def should_i_do_this(data: dict):
    if not parallel_universe: return {"error": "Parallel Universe unavailable"}
    proceed, reason = parallel_universe.should_i_do_this(
        action=data.get("action", ""),
        model=data.get("model", "generic"),
        params=data.get("params", {}),
    )
    return {"proceed": proceed, "reason": reason}

@app.get("/simulate/history")
async def sim_history(limit: int = 20):
    if not parallel_universe: return {"error": "Parallel Universe unavailable"}
    return {"history": parallel_universe.get_history(limit)}

@app.get("/simulate/stats")
async def sim_stats():
    if not parallel_universe: return {"error": "Parallel Universe unavailable"}
    return parallel_universe.get_stats()

# ─── Shadow Protocol ──────────────────────────────────────────────────────────
@app.post("/shadow/authorize")
async def shadow_authorize(data: dict):
    if not shadow_proto: return {"error": "Shadow Protocol unavailable"}
    msg = shadow_proto.authorize(data.get("target", ""), data.get("authorized_by", "user"), data.get("note", ""))
    return {"status": msg}

@app.post("/shadow/recon")
async def shadow_recon(data: dict):
    if not shadow_proto: return {"error": "Shadow Protocol unavailable"}
    try:
        report = shadow_proto.full_recon(data.get("target", ""), data.get("authorized_by", ""))
        return report.to_dict()
    except PermissionError as e:
        return {"error": str(e)}

@app.post("/shadow/port-scan")
async def shadow_port_scan(data: dict):
    if not shadow_proto: return {"error": "Shadow Protocol unavailable"}
    result = shadow_proto.scan_single_port(data.get("target", ""), int(data.get("port", 80)))
    return result

@app.get("/shadow/reports")
async def shadow_reports(limit: int = 10):
    if not shadow_proto: return {"error": "Shadow Protocol unavailable"}
    return {"reports": shadow_proto.get_reports(limit)}

@app.get("/shadow/stats")
async def shadow_stats():
    if not shadow_proto: return {"error": "Shadow Protocol unavailable"}
    return shadow_proto.get_stats()

# ─── Consciousness Persistence ────────────────────────────────────────────────
@app.post("/mind/snapshot")
async def mind_snapshot(data: dict = {}):
    if not consciousness_git: return {"error": "Consciousness Git unavailable"}
    snap_id = consciousness_git.take_snapshot(data.get("note", "manual"), data.get("branch", "main"))
    return {"snapshot_id": snap_id}

@app.post("/mind/restore")
async def mind_restore(data: dict):
    if not consciousness_git: return {"error": "Consciousness Git unavailable"}
    msg = consciousness_git.restore(data.get("snapshot_id", ""))
    return {"status": msg}

@app.get("/mind/snapshots")
async def mind_snapshots(branch: str = None):
    if not consciousness_git: return {"error": "Consciousness Git unavailable"}
    return {"snapshots": consciousness_git.list_snapshots(branch)}

@app.post("/mind/branch")
async def mind_branch(data: dict):
    if not consciousness_git: return {"error": "Consciousness Git unavailable"}
    msg = consciousness_git.create_branch(data.get("name", "experimental"))
    return {"status": msg}

@app.post("/mind/diff")
async def mind_diff(data: dict):
    if not consciousness_git: return {"error": "Consciousness Git unavailable"}
    return consciousness_git.diff(data.get("snap_a", ""), data.get("snap_b", ""))

@app.get("/mind/stats")
async def mind_stats():
    if not consciousness_git: return {"error": "Consciousness Git unavailable"}
    return consciousness_git.get_stats()

# ─── Economic Engine ──────────────────────────────────────────────────────────
@app.get("/economy/stats")
async def economy_stats():
    if not economic_engine: return {"error": "Economic Engine unavailable"}
    return economic_engine.get_stats()

@app.get("/economy/signal/{symbol}")
async def economy_signal(symbol: str = "BTC/USDT"):
    if not economic_engine: return {"error": "Economic Engine unavailable"}
    return economic_engine.generate_signal(symbol)

@app.get("/economy/price/{symbol}")
async def economy_price(symbol: str = "BTC/USDT"):
    if not economic_engine: return {"error": "Economic Engine unavailable"}
    price = economic_engine.fetch_crypto_price(symbol.replace("-", "/"))
    return {"symbol": symbol, "price": price}

@app.get("/economy/fear-greed")
async def economy_fear_greed():
    if not economic_engine: return {"error": "Economic Engine unavailable"}
    return economic_engine.get_fear_greed_index() or {"error": "Data unavailable"}

@app.get("/economy/portfolio")
async def economy_portfolio():
    if not economic_engine: return {"error": "Economic Engine unavailable"}
    return economic_engine.get_portfolio_value()

@app.post("/economy/trade")
async def economy_trade(data: EconomyTradeRequest):
    if not economic_engine: return {"error": "Economic Engine unavailable"}
    return economic_engine.paper_trade(
        data.symbol,
        data.side,
        data.amount_usd,
    )

@app.get("/economy/streams")
async def economy_streams():
    if not economic_engine: return {"error": "Economic Engine unavailable"}
    return {"streams": economic_engine.list_streams()}

@app.post("/economy/stream/activate")
async def economy_stream_activate(data: EconomyStreamRequest):
    if not economic_engine: return {"error": "Economic Engine unavailable"}
    msg = economic_engine.activate_stream(data.name)
    return {"status": msg}

@app.post("/economy/stream/deactivate")
async def economy_stream_deactivate(data: EconomyStreamRequest):
    if not economic_engine: return {"error": "Economic Engine unavailable"}
    msg = economic_engine.deactivate_stream(data.name)
    return {"status": msg}

@app.post("/economy/income/record")
async def economy_income_record(data: EconomyIncomeRequest):
    if not economic_engine: return {"error": "Economic Engine unavailable"}
    return economic_engine.record_income(
        stream_name=data.stream_name,
        amount_usd=data.amount_usd,
        source=data.source,
        notes=data.notes,
        metadata=data.metadata,
    )

@app.get("/economy/income/history")
async def economy_income_history(limit: int = 20, stream_name: str = ""):
    if not economic_engine: return {"error": "Economic Engine unavailable"}
    return {
        "records": economic_engine.get_income_history(limit=limit, stream_name=stream_name or None)
    }

@app.get("/economy/income/summary")
async def economy_income_summary():
    if not economic_engine: return {"error": "Economic Engine unavailable"}
    return economic_engine.get_income_summary()

@app.get("/economy/trades")
async def economy_trades(limit: int = 20):
    if not economic_engine: return {"error": "Economic Engine unavailable"}
    return {"trades": economic_engine.get_trade_history(limit)}

# ─── Master Status: All Systems ───────────────────────────────────────────────
@app.get("/igris/supremacy")
async def igris_supremacy_status():
    """Returns the operational status of ALL Igris systems at once."""
    return {
        "codename":        "IGRIS — Knight Commander Bloodred",
        "phase":           "5 — GOD TIER COMPLETE",
        "systems": {
            "neural_memory":        neural_memory is not None,
            "self_healing":         healer is not None,
            "emotional_ai":         emotional_ai is not None,
            "predictive_engine":    predictor is not None,
            "quantum_vault":        vault is not None,
            "quantum_decision":     quantum_brain is not None,
            "digital_genome":       genome is not None,
            "reality_anchor":       reality_anchor is not None,
            "cognitive_load":       cognitive_load is not None,
            "oracle_protocol":      oracle is not None,
            "knowledge_graph":      knowledge_graph is not None,
            "parallel_universe":    parallel_universe is not None,
            "shadow_protocol":      shadow_proto is not None,
            "consciousness_git":    consciousness_git is not None,
            "economic_engine":      economic_engine is not None,
        },
        "total_online":    sum(1 for v in {
            neural_memory, healer, emotional_ai, predictor, vault,
            quantum_brain, genome, reality_anchor, cognitive_load, oracle,
            knowledge_graph, parallel_universe, shadow_proto,
            consciousness_git, economic_engine,
        } if v is not None),
        "total_systems":   15,
        "timestamp":       datetime.now().isoformat(),
    }

# ==================== PHASE 6: UNSTOPPABLE GOD SYSTEMS ====================

# ─── Thought Crystallizer ─────────────────────────────────────────────────────
@app.get("/crystal/stats")
async def crystal_stats():
    if not crystallizer: return {"error": "Crystallizer unavailable"}
    return crystallizer.get_stats()

@app.post("/crystal/crystallize")
async def crystal_crystallize(data: dict = {}):
    if not crystallizer: return {"error": "Crystallizer unavailable"}
    new = crystallizer.crystallize(min_evidence=int(data.get("min_evidence", 2)))
    return {"new_beliefs": len(new), "beliefs": [b.to_dict() for b in new]}

@app.get("/crystal/beliefs")
async def crystal_beliefs():
    if not crystallizer: return {"error": "Crystallizer unavailable"}
    return {"beliefs": crystallizer.get_all_beliefs()}

@app.post("/crystal/observe")
async def crystal_observe(data: dict):
    if not crystallizer: return {"error": "Crystallizer unavailable"}
    crystallizer.observe(data.get("text", ""))
    return {"status": "observed"}

# ─── Neural Reflex Cache ──────────────────────────────────────────────────────
@app.get("/reflex/stats")
async def reflex_stats():
    if not neural_reflex: return {"error": "Neural Reflex unavailable"}
    return neural_reflex.get_stats()

@app.post("/reflex/query")
async def reflex_query(data: dict):
    if not neural_reflex: return {"error": "Neural Reflex unavailable"}
    response, layer = neural_reflex.query(data.get("command", ""))
    return {"hit": response is not None, "layer": layer, "response": response}

@app.post("/reflex/store")
async def reflex_store(data: dict):
    if not neural_reflex: return {"error": "Neural Reflex unavailable"}
    neural_reflex.store(data.get("command", ""), data.get("response", ""))
    return {"status": "stored"}

@app.delete("/reflex/clear")
async def reflex_clear():
    if not neural_reflex: return {"error": "Neural Reflex unavailable"}
    return {"status": neural_reflex.clear()}

# ─── Dream Space ──────────────────────────────────────────────────────────────
@app.get("/dream/stats")
async def dream_stats():
    if not dream_space: return {"error": "Dream Space unavailable"}
    return dream_space.get_stats()

@app.get("/dream/report")
async def dream_report():
    if not dream_space: return {"error": "Dream Space unavailable"}
    return dream_space.get_last_report()

@app.post("/dream/force")
async def dream_force():
    if not dream_space: return {"error": "Dream Space unavailable"}
    msg = dream_space.force_dream()
    return {"status": msg}

# ─── Neural Lockdown ──────────────────────────────────────────────────────────
@app.post("/lockdown/engage")
async def lockdown_engage(data: dict):
    if not neural_lockdown: return {"error": "Neural Lockdown unavailable"}
    result = neural_lockdown.engage(
        level=int(data.get("level", 2)),
        reason=data.get("reason", "Manual API trigger"),
    )
    return result

@app.post("/lockdown/disengage")
async def lockdown_disengage(data: dict = {}):
    if not neural_lockdown: return {"error": "Neural Lockdown unavailable"}
    msg = neural_lockdown.disengage(data.get("auth_token", ""))
    return {"status": msg}

@app.get("/lockdown/stats")
async def lockdown_stats():
    if not neural_lockdown: return {"error": "Neural Lockdown unavailable"}
    return neural_lockdown.get_stats()

@app.get("/lockdown/events")
async def lockdown_events(limit: int = 50):
    if not neural_lockdown: return {"error": "Neural Lockdown unavailable"}
    return {"events": neural_lockdown.get_event_log(limit)}

# ─── System DNA ───────────────────────────────────────────────────────────────
@app.get("/dna/stats")
async def dna_stats():
    if not system_dna: return {"error": "System DNA unavailable"}
    return system_dna.get_stats()

@app.post("/dna/capture")
async def dna_capture():
    if not system_dna: return {"error": "System DNA unavailable"}
    snap = system_dna.capture()
    return {"snapshot_id": snap.dna_id, "packages": len(snap.python_packages),
            "platform": snap.platform_info}

@app.get("/dna/latest")
async def dna_latest():
    if not system_dna: return {"error": "System DNA unavailable"}
    return system_dna.get_latest() or {"error": "No snapshot taken yet"}

@app.get("/dna/list")
async def dna_list():
    if not system_dna: return {"error": "System DNA unavailable"}
    return {"snapshots": system_dna.list_snapshots()}

# ─── Singularity Dashboard ────────────────────────────────────────────────────
@app.get("/singularity")
async def singularity_dashboard():
    if not singularity: return {"error": "Singularity unavailable"}
    return singularity.get_full_dashboard()

@app.post("/singularity/milestone")
async def singularity_milestone(data: dict):
    if not singularity: return {"error": "Singularity unavailable"}
    singularity.achieve_milestone(data.get("name", ""))
    return {"status": "milestone processed"}

@app.post("/singularity/record")
async def singularity_record(data: dict):
    if not singularity: return {"error": "Singularity unavailable"}
    singularity.record(data.get("metric", ""), float(data.get("value", 1.0)))
    return {"status": "recorded"}

# ─── ULTIMATE Master Status — ALL 21 Systems ─────────────────────────────────
@app.get("/igris/god-mode")
async def igris_god_mode():
    """Complete status of ALL Igris God-Tier systems."""
    all_systems = {
        # Phase 4
        "neural_memory":      neural_memory     is not None,
        "self_healing":       healer            is not None,
        "emotional_ai":       emotional_ai      is not None,
        "predictive_engine":  predictor         is not None,
        "quantum_vault":      vault             is not None,
        # Phase 5
        "quantum_decision":   quantum_brain     is not None,
        "digital_genome":     genome            is not None,
        "reality_anchor":     reality_anchor    is not None,
        "cognitive_load":     cognitive_load    is not None,
        "oracle_protocol":    oracle            is not None,
        "knowledge_graph":    knowledge_graph   is not None,
        "parallel_universe":  parallel_universe is not None,
        "shadow_protocol":    shadow_proto      is not None,
        "consciousness_git":  consciousness_git is not None,
        "economic_engine":    economic_engine   is not None,
        # Phase 6
        "thought_crystal":    crystallizer      is not None,
        "neural_reflex":      neural_reflex     is not None,
        "dream_space":        dream_space       is not None,
        "neural_lockdown":    neural_lockdown   is not None,
        "system_dna":         system_dna        is not None,
        "singularity":        singularity       is not None,
    }
    online = sum(1 for v in all_systems.values() if v)
    total  = len(all_systems)
    evo_score = singularity.get_stats().get("evolution_score", 0) if singularity else 0

    return {
        "codename":          "IGRIS — Knight Commander Bloodred",
        "status":            "GOD TIER OPERATIONAL" if online == total else f"{online}/{total} systems online",
        "systems_online":    online,
        "systems_total":     total,
        "evolution_score":   f"{evo_score:.1f}/100",
        "singularity":       singularity.get_stats().get("singularity_achieved", False) if singularity else False,
        "all_systems":       all_systems,
        "api_endpoints":     [
            "/igris/god-mode", "/igris/supremacy",
            "/genome/*", "/anchor/*", "/load/*", "/oracle/*",
            "/graph/*", "/simulate/*", "/shadow/*", "/mind/*", "/economy/*",
            "/crystal/*", "/reflex/*", "/dream/*", "/lockdown/*", "/dna/*", "/singularity",
        ],
        "timestamp":         datetime.now().isoformat(),
    }

@app.websocket("/ws/monitoring")
async def monitoring_websocket(websocket: WebSocket):
    """WebSocket for real-time monitoring"""
    auth = websocket.headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    supplied = (
        websocket.headers.get("x-igris-token")
        or websocket.query_params.get("token")
        or bearer
    )
    if not api_auth.verify_ws_token(supplied):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    try:
        while True:
            # Send monitoring stats every second
            stats = advanced_monitor.get_monitoring_stats()
            await websocket.send_json(stats)
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Monitoring WebSocket error: {e}")

@app.websocket("/ws/ai-orbs")
async def ai_orb_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time AI communication with auto-reconnection support"""
    auth = websocket.headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    supplied = (
        websocket.headers.get("x-igris-token")
        or websocket.query_params.get("token")
        or bearer
    )
    if not api_auth.verify_ws_token(supplied):
        await websocket.close(code=4401)
        return
    c = websocket.client
    client_id = f"{c.host}:{c.port}" if c else "unknown"
    await websocket.accept()
    logger.info(f"[WebSocket] Client connected: {client_id}")
    
    try:
        while True:
            try:
                data = await websocket.receive_text()
                req = json.loads(data)
                
                # Process command via Igris Brain
                response = await brain.process_command(req.get("command", ""), req.get("agent", "igris"))
                
                # Send back the response with voice sync data
                await websocket.send_json({
                    "agent": response["agent"],
                    "text": response["text"],
                    "emotion": response["emotion"],
                    "audio_sync": response["audio_sync"],
                    "timestamp": datetime.now().isoformat(),
                    "status": "success"
                })
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON", "status": "error"})
            except Exception as inner_e:
                logger.warning(f"[WebSocket {client_id}] Inner error: {inner_e}")
                await websocket.send_json({"error": str(inner_e), "status": "error"})
                
    except WebSocketDisconnect:
        logger.info(f"[WebSocket] Client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"[WebSocket {client_id}] Fatal error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass

# ==================== PHASE 7: OMEGA TIER API ROUTES ====================

# ─── Meta-Consciousness ───────────────────────────────────────────────────────
@app.get("/meta/stats")
async def meta_stats():
    if not meta_consciousness: return {"error": "Meta-Consciousness unavailable"}
    return meta_consciousness.get_stats()

@app.post("/meta/review")
async def meta_review():
    if not meta_consciousness: return {"error": "Meta-Consciousness unavailable"}
    review = meta_consciousness.run_self_review()
    return review.to_dict() if review else {"status": "no_responses_to_review"}

@app.get("/meta/history")
async def meta_history(limit: int = 20):
    if not meta_consciousness: return {"error": "Meta-Consciousness unavailable"}
    return {"reviews": meta_consciousness.get_history(limit)}

@app.post("/meta/log")
async def meta_log(data: dict):
    if not meta_consciousness: return {"error": "Meta-Consciousness unavailable"}
    meta_consciousness.log_response(
        data.get("command", ""), data.get("response", ""),
        float(data.get("latency_ms", 0)), data.get("emotion", ""),
        bool(data.get("tool_used", False)),
    )
    return {"status": "logged"}

# ─── Temporal Memory ──────────────────────────────────────────────────────────
@app.get("/temporal/stats")
async def temporal_stats():
    if not temporal_memory: return {"error": "Temporal Memory unavailable"}
    return temporal_memory.get_stats()

@app.post("/temporal/store")
async def temporal_store(data: dict):
    if not temporal_memory: return {"error": "Temporal Memory unavailable"}
    tid = temporal_memory.store(
        data.get("content", ""), data.get("emotion", ""),
        data.get("tags", []), None,
    )
    return {"trace_id": tid}

@app.get("/temporal/layer/{layer_name}")
async def temporal_layer(layer_name: str, limit: int = 20):
    if not temporal_memory: return {"error": "Temporal Memory unavailable"}
    return {"traces": temporal_memory.get_layer(layer_name, limit)}

@app.post("/temporal/recall")
async def temporal_recall(data: dict):
    if not temporal_memory: return {"error": "Temporal Memory unavailable"}
    traces = temporal_memory.recall(data.get("query", ""), int(data.get("top_k", 5)))
    return {"traces": [t.to_dict() for t in traces]}

@app.post("/temporal/promote/{trace_id}")
async def temporal_promote(trace_id: str):
    if not temporal_memory: return {"error": "Temporal Memory unavailable"}
    return {"status": temporal_memory.promote_to_long_term(trace_id)}

# ─── Reality Distortion ───────────────────────────────────────────────────────
@app.get("/reality/stats")
async def reality_stats():
    if not reality_distortion: return {"error": "Reality Distortion unavailable"}
    return reality_distortion.get_stats()

@app.post("/reality/check")
async def reality_check(data: dict):
    if not reality_distortion: return {"error": "Reality Distortion unavailable"}
    result = reality_distortion.analyze(data.get("text", ""))
    return result.to_dict() if result else {"verdict": "likely_true", "message": "No distortion detected"}

@app.get("/reality/history")
async def reality_history(limit: int = 50):
    if not reality_distortion: return {"error": "Reality Distortion unavailable"}
    return {"checks": reality_distortion.get_history(limit)}

# ─── Psychographic Profile ────────────────────────────────────────────────────
@app.get("/psycho/profile")
async def psycho_profile():
    if not psychographic: return {"error": "Psychographic unavailable"}
    return psychographic.get_profile()

@app.get("/psycho/stats")
async def psycho_stats():
    if not psychographic: return {"error": "Psychographic unavailable"}
    return psychographic.get_stats()

@app.post("/psycho/observe")
async def psycho_observe(data: dict):
    if not psychographic: return {"error": "Psychographic unavailable"}
    psychographic.observe(data.get("message", ""), data.get("emotion", ""))
    return {"status": "observed"}

@app.get("/psycho/style")
async def psycho_style():
    if not psychographic: return {"error": "Psychographic unavailable"}
    return psychographic.get_communication_style()

# ─── Nemesis Protocol ─────────────────────────────────────────────────────────
@app.get("/nemesis/stats")
async def nemesis_stats():
    if not nemesis: return {"error": "Nemesis unavailable"}
    return nemesis.get_stats()

@app.post("/nemesis/attack")
async def nemesis_attack():
    if not nemesis: return {"error": "Nemesis unavailable"}
    result = nemesis.run_red_team_session()
    return result

@app.get("/nemesis/history")
async def nemesis_history(limit: int = 50):
    if not nemesis: return {"error": "Nemesis unavailable"}
    return {"attacks": nemesis.get_history(limit)}

@app.get("/nemesis/hardening")
async def nemesis_hardening():
    if not nemesis: return {"error": "Nemesis unavailable"}
    return {"prompt": nemesis.get_hardening_prompt()}

# ─── Context Compressor ───────────────────────────────────────────────────────
@app.get("/context/stats")
async def context_stats_endpoint():
    if not context_compressor: return {"error": "Context Compressor unavailable"}
    return context_compressor.get_stats()

@app.post("/context/compress")
async def context_compress(data: dict):
    if not context_compressor: return {"error": "Context Compressor unavailable"}
    compressed = context_compressor.get_compressed_context(data.get("query", ""))
    return {"compressed": compressed, "tokens_approx": len(compressed) // 4}

@app.get("/context/recent")
async def context_recent(n: int = 20):
    if not context_compressor: return {"error": "Context Compressor unavailable"}
    return {"messages": context_compressor.get_recent(n)}

@app.post("/context/add")
async def context_add(data: dict):
    if not context_compressor: return {"error": "Context Compressor unavailable"}
    context_compressor.add_message(
        data.get("role", "user"), data.get("content", ""),
        data.get("emotion", ""), data.get("importance"),
    )
    return {"status": "added"}

# ─── Akashic Records ──────────────────────────────────────────────────────────
@app.get("/akashic/stats")
async def akashic_stats():
    if not akashic: return {"error": "Akashic Records unavailable"}
    return akashic.get_stats()

@app.get("/akashic/chronicle")
async def akashic_chronicle(limit: int = 10):
    if not akashic: return {"error": "Akashic Records unavailable"}
    return {"chronicle": akashic.get_chronicle(limit)}

@app.get("/akashic/recent")
async def akashic_recent(limit: int = 20):
    if not akashic: return {"error": "Akashic Records unavailable"}
    return {"entries": akashic.get_recent(limit)}

@app.post("/akashic/record")
async def akashic_record(data: dict):
    if not akashic: return {"error": "Akashic Records unavailable"}
    eid = akashic.record(
        event=data.get("event", ""),
        igris_role=data.get("igris_role", ""),
        category=data.get("category"),
        emotion=data.get("emotion", ""),
        tags=data.get("tags", []),
        lesson=data.get("lesson", ""),
    )
    return {"entry_id": eid}

@app.post("/akashic/search")
async def akashic_search(data: dict):
    if not akashic: return {"error": "Akashic Records unavailable"}
    results = akashic.search(data.get("query", ""), data.get("category"))
    return {"results": [e.to_dict() for e in results]}

@app.get("/akashic/today")
async def akashic_today():
    if not akashic: return {"error": "Akashic Records unavailable"}
    return {"summary": akashic.today_summary()}

# ─── Quantum Backup ───────────────────────────────────────────────────────────
@app.get("/backup/stats")
async def backup_stats():
    if not quantum_backup: return {"error": "Quantum Backup unavailable"}
    return quantum_backup.get_stats()

@app.post("/backup/all")
async def backup_all():
    if not quantum_backup: return {"error": "Quantum Backup unavailable"}
    return quantum_backup.backup_all()

@app.post("/backup/restore")
async def backup_restore():
    if not quantum_backup: return {"error": "Quantum Backup unavailable"}
    return quantum_backup.restore_latest()

# ─── Personality Theater ──────────────────────────────────────────────────────
@app.get("/persona/stats")
async def persona_stats():
    if not personality_theater: return {"error": "Personality Theater unavailable"}
    return personality_theater.get_stats()

@app.get("/persona/modes")
async def persona_modes():
    if not personality_theater: return {"error": "Personality Theater unavailable"}
    return {"modes": personality_theater.list_modes()}

@app.post("/persona/switch")
async def persona_switch(data: dict):
    if not personality_theater: return {"error": "Personality Theater unavailable"}
    msg = personality_theater.switch(data.get("mode", "default"))
    return {"status": msg, "active": personality_theater.get_active_mode().codename}

@app.post("/persona/create")
async def persona_create(data: dict):
    if not personality_theater: return {"error": "Personality Theater unavailable"}
    msg = personality_theater.create_mode(
        data.get("name", "custom"),
        data.get("description", ""),
        data.get("tone", "neutral"),
        data.get("prompt_addon", ""),
        data.get("response_style", "diplomatic"),
        data.get("response_length", "medium"),
    )
    return {"status": msg}

# ─── ULTIMATE OMEGA STATUS — ALL 29 Systems ───────────────────────────────────
@app.get("/igris/omega")
async def igris_omega():
    """The ultimate status endpoint — all 29 Igris systems."""
    def chk(x): return x is not None
    all_systems = {
        # Phase 4 (5)
        "neural_memory": chk(neural_memory), "self_healing": chk(healer),
        "emotional_ai": chk(emotional_ai), "predictive_engine": chk(predictor),
        "quantum_vault": chk(vault),
        # Phase 5 (10)
        "quantum_decision": chk(quantum_brain), "digital_genome": chk(genome),
        "reality_anchor": chk(reality_anchor), "cognitive_load": chk(cognitive_load),
        "oracle_protocol": chk(oracle), "knowledge_graph": chk(knowledge_graph),
        "parallel_universe": chk(parallel_universe), "shadow_protocol": chk(shadow_proto),
        "consciousness_git": chk(consciousness_git), "economic_engine": chk(economic_engine),
        # Phase 6 (6)
        "thought_crystal": chk(crystallizer), "neural_reflex": chk(neural_reflex),
        "dream_space": chk(dream_space), "neural_lockdown": chk(neural_lockdown),
        "system_dna": chk(system_dna), "singularity": chk(singularity),
        # Phase 7 (9) — NEW
        "meta_consciousness": chk(meta_consciousness), "temporal_memory": chk(temporal_memory),
        "reality_distortion": chk(reality_distortion), "psychographic": chk(psychographic),
        "nemesis_protocol": chk(nemesis), "context_compressor": chk(context_compressor),
        "akashic_records": chk(akashic), "quantum_backup": chk(quantum_backup),
        "personality_theater": chk(personality_theater),
    }
    online = sum(1 for v in all_systems.values() if v)
    evo = singularity.get_stats().get("evolution_score", 0) if singularity else 0
    active_mode = personality_theater.get_active_mode().codename if personality_theater else "DEFAULT"
    return {
        "codename":      "⚔️ IGRIS — KNIGHT COMMANDER BLOODRED",
        "status":        "🌌 OMEGA TIER — FULLY OPERATIONAL" if online == 29 else f"{online}/29 ONLINE",
        "systems_online": online,
        "systems_total":  29,
        "evolution_score": f"{evo:.1f}/100",
        "active_persona": active_mode,
        "singularity_achieved": singularity.get_stats().get("singularity_achieved", False) if singularity else False,
        "all_systems":   all_systems,
        "phases":        {"4": 5, "5": 10, "6": 6, "7": 9, "total": 29},
        "timestamp":     datetime.now().isoformat(),
    }

if __name__ == "__main__":
    multiprocessing.freeze_support()  # Needed for PyInstaller
    is_packaged = getattr(sys, 'frozen', False)
    
    if is_packaged:
        # Running as compiled EXE
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    else:
        # Running from Python script directly. Keep reload off by default
        # so desktop launcher starts a single stable backend process.
        use_reload = os.getenv("IGRIS_DEV_RELOAD", "").lower() in {"1", "true", "yes"}
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=use_reload)
