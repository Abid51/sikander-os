"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS SELF-HEALING ENGINE
  Auto-detects errors, takes snapshots, restores state, and heals
  Features: File snapshot/rollback, error pattern learning,
            circuit breaker auto-reset, health pulse monitoring
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import shutil
import time
import traceback
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Tuple

import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ErrorRecord:
    id: str
    error_type: str
    message: str
    traceback_str: str
    module: str
    count: int = 1
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    auto_healed: bool = False
    heal_action: str = ""


@dataclass
class FileSnapshot:
    path: str
    content_hash: str
    size: int
    backup_path: str
    created_at: float = field(default_factory=time.time)


@dataclass
class HealthPulse:
    component: str
    status: str          # "healthy" | "degraded" | "critical" | "dead"
    latency_ms: float
    last_check: float
    consecutive_failures: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
#  SELF-HEALING ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class SelfHealingEngine:
    """
    Igris's autonomous self-repair system.

    Capabilities
    ────────────
    • Captures errors and learns patterns
    • Takes file snapshots before risky operations
    • Auto-rollback corrupted files
    • Health pulse monitoring with auto-restart
    • Circuit breaker pattern for failing subsystems
    • Self-healing decorators for any async function
    """

    BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "backups", "healer")
    MAX_ERROR_HISTORY = 500
    MAX_SNAPSHOTS_PER_FILE = 5

    def __init__(self) -> None:
        self._errors: Dict[str, ErrorRecord] = {}     # fingerprint -> record
        self._error_timeline: List[dict] = []
        self._snapshots: Dict[str, List[FileSnapshot]] = defaultdict(list)
        self._health: Dict[str, HealthPulse] = {}
        self._circuit_breakers: Dict[str, dict] = {}   # name -> {state, failures, ...}
        self._heal_count = 0
        self._started_at = time.time()
        self._heal_log: List[dict] = []

        os.makedirs(self.BACKUP_DIR, exist_ok=True)
        logger.info("[SELF-HEALER] ⚡ Engine online — watching for anomalies.")

    # ── Error Capture ─────────────────────────────────────────────────────────

    def capture_error(self, exc: Exception, module: str = "unknown", context: str = "") -> ErrorRecord:
        """Capture and analyze an error."""
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb_str = "".join(tb[-5:])   # last 5 frames
        fingerprint = hashlib.md5(f"{type(exc).__name__}:{module}:{str(exc)[:100]}".encode()).hexdigest()[:12]

        if fingerprint in self._errors:
            rec = self._errors[fingerprint]
            rec.count += 1
            rec.last_seen = time.time()
        else:
            rec = ErrorRecord(
                id=fingerprint,
                error_type=type(exc).__name__,
                message=str(exc)[:500],
                traceback_str=tb_str,
                module=module,
            )
            self._errors[fingerprint] = rec

        self._error_timeline.append({
            "id": fingerprint,
            "type": rec.error_type,
            "module": module,
            "message": str(exc)[:200],
            "context": context,
            "timestamp": time.time(),
        })
        if len(self._error_timeline) > self.MAX_ERROR_HISTORY:
            self._error_timeline.pop(0)

        # Auto-heal attempt
        self._try_auto_heal(rec, exc, module)

        return rec

    def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Test / convenience API: record the error and return a result dict
        (see :meth:`capture_error`).
        """
        context = context or {}
        mod = str(context.get("module") or context.get("operation") or "unknown")
        self.capture_error(error, module=mod, context=str(context)[:500])
        return {
            "status":  "recorded",
            "handled": True,
            "error":   type(error).__name__,
            "message": str(error)[:200],
        }

    def _try_auto_heal(self, rec: ErrorRecord, exc: Exception, module: str) -> None:
        """Attempt automatic healing based on error pattern."""
        healed = False
        action = ""

        # Pattern: file corruption → rollback
        if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError)):
            for fpath, snaps in self._snapshots.items():
                if module in fpath or fpath in str(exc):
                    if snaps:
                        self.rollback(fpath)
                        action = f"Rolled back {fpath} to last snapshot"
                        healed = True
                        break

        # Pattern: import error → log + skip
        elif isinstance(exc, (ImportError, ModuleNotFoundError)):
            action = f"Module '{exc.name if hasattr(exc, 'name') else module}' missing — marked as optional"
            healed = True  # Not a true fix but prevents crash loop

        # Pattern: repeated failures → circuit breaker
        if rec.count >= 5 and not healed:
            cb_name = f"auto_{module}"
            self._trip_circuit_breaker(cb_name)
            action = f"Circuit breaker tripped for {module} after {rec.count} failures"
            healed = True

        if healed:
            rec.auto_healed = True
            rec.heal_action = action
            self._heal_count += 1
            self._heal_log.append({
                "error_id": rec.id,
                "action": action,
                "timestamp": time.time(),
            })
            logger.info(f"[SELF-HEALER] 🩺 Auto-healed: {action}")

    # ── File Snapshots ────────────────────────────────────────────────────────

    def snapshot(self, file_path: str) -> Optional[FileSnapshot]:
        """Take a backup snapshot of a file."""
        file_path = os.path.abspath(file_path)
        if not os.path.isfile(file_path):
            return None

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            content_hash = hashlib.sha256(content).hexdigest()[:16]

            # Check if identical to last snapshot
            existing = self._snapshots.get(file_path, [])
            if existing and existing[-1].content_hash == content_hash:
                return existing[-1]  # No change

            backup_name = f"{os.path.basename(file_path)}.{content_hash}.bak"
            backup_path = os.path.join(self.BACKUP_DIR, backup_name)
            shutil.copy2(file_path, backup_path)

            snap = FileSnapshot(
                path=file_path,
                content_hash=content_hash,
                size=len(content),
                backup_path=backup_path,
            )
            self._snapshots[file_path].append(snap)

            # Keep only last N snapshots
            while len(self._snapshots[file_path]) > self.MAX_SNAPSHOTS_PER_FILE:
                old = self._snapshots[file_path].pop(0)
                try:
                    os.unlink(old.backup_path)
                except OSError:
                    pass

            return snap
        except Exception as e:
            logger.error(f"[SELF-HEALER] Snapshot failed for {file_path}: {e}")
            return None

    def rollback(self, file_path: str) -> str:
        """Rollback a file to its last snapshot."""
        file_path = os.path.abspath(file_path)
        snaps = self._snapshots.get(file_path, [])
        if not snaps:
            return f"No snapshots available for {file_path}"
        
        latest = snaps[-1]
        if not os.path.isfile(latest.backup_path):
            return f"Backup file missing: {latest.backup_path}"

        try:
            shutil.copy2(latest.backup_path, file_path)
            self._heal_count += 1
            msg = f"Rolled back {os.path.basename(file_path)} to snapshot {latest.content_hash}"
            logger.info(f"[SELF-HEALER] 🔄 {msg}")
            return msg
        except Exception as e:
            return f"Rollback failed: {e}"

    def get_snapshots(self, file_path: str = None) -> dict:
        if file_path:
            return {"file": file_path, "snapshots": [asdict(s) for s in self._snapshots.get(os.path.abspath(file_path), [])]}
        return {fp: [asdict(s) for s in snaps] for fp, snaps in self._snapshots.items()}

    # ── Health Monitoring ─────────────────────────────────────────────────────

    def register_health_check(self, component: str) -> None:
        self._health[component] = HealthPulse(
            component=component, status="unknown", latency_ms=0, last_check=0
        )

    async def check_health(self, component: str, check_fn: Callable) -> HealthPulse:
        """Run a health check function and record result."""
        t = time.time()
        try:
            result = await check_fn() if asyncio.iscoroutinefunction(check_fn) else check_fn()
            latency = (time.time() - t) * 1000

            pulse = self._health.get(component, HealthPulse(
                component=component, status="unknown", latency_ms=0, last_check=0
            ))

            if result:
                pulse.status = "healthy" if latency < 1000 else "degraded"
                pulse.consecutive_failures = 0
            else:
                pulse.consecutive_failures += 1
                pulse.status = "critical" if pulse.consecutive_failures >= 3 else "degraded"

            pulse.latency_ms = round(latency, 1)
            pulse.last_check = time.time()
            pulse.details = result if isinstance(result, dict) else {"result": result}
            self._health[component] = pulse
            return pulse

        except Exception as e:
            pulse = self._health.get(component, HealthPulse(
                component=component, status="unknown", latency_ms=0, last_check=0
            ))
            pulse.status = "dead"
            pulse.consecutive_failures += 1
            pulse.latency_ms = round((time.time() - t) * 1000, 1)
            pulse.last_check = time.time()
            pulse.details = {"error": str(e)}
            self._health[component] = pulse
            self.capture_error(e, module=f"health_{component}")
            return pulse

    def get_health_report(self) -> dict:
        report = {}
        for comp, pulse in self._health.items():
            report[comp] = asdict(pulse)
        return report

    # ── Circuit Breakers ──────────────────────────────────────────────────────

    def _trip_circuit_breaker(self, name: str) -> None:
        self._circuit_breakers[name] = {
            "state": "open",
            "tripped_at": time.time(),
            "cooldown_secs": 60,
            "failure_count": self._circuit_breakers.get(name, {}).get("failure_count", 0) + 1,
        }

    def is_circuit_open(self, name: str) -> bool:
        cb = self._circuit_breakers.get(name)
        if not cb or cb["state"] != "open":
            return False
        # Auto-reset after cooldown
        if time.time() - cb["tripped_at"] > cb["cooldown_secs"]:
            cb["state"] = "half-open"
            return False
        return True

    def reset_circuit(self, name: str) -> None:
        if name in self._circuit_breakers:
            self._circuit_breakers[name]["state"] = "closed"

    # ── Decorator ─────────────────────────────────────────────────────────────

    def heal(self, module: str = "unknown"):
        """Decorator that auto-captures errors and attempts healing."""
        def decorator(fn):
            async def wrapper(*args, **kwargs):
                try:
                    return await fn(*args, **kwargs) if asyncio.iscoroutinefunction(fn) else fn(*args, **kwargs)
                except Exception as exc:
                    self.capture_error(exc, module=module, context=fn.__name__)
                    raise
            wrapper.__name__ = fn.__name__
            wrapper.__doc__ = fn.__doc__
            return wrapper
        return decorator

    # ── Stats / History ───────────────────────────────────────────────────────

    def get_error_history(self, limit: int = 50) -> List[dict]:
        return self._error_timeline[-limit:]

    def get_stats(self) -> dict:
        error_types: Dict[str, int] = defaultdict(int)
        for rec in self._errors.values():
            error_types[rec.error_type] += rec.count

        return {
            "uptime_secs": round(time.time() - self._started_at, 1),
            "total_errors_captured": sum(r.count for r in self._errors.values()),
            "unique_errors": len(self._errors),
            "auto_heals": self._heal_count,
            "error_types": dict(error_types),
            "file_snapshots": sum(len(s) for s in self._snapshots.values()),
            "circuit_breakers": {
                name: cb["state"] for name, cb in self._circuit_breakers.items()
            },
            "health_components": len(self._health),
            "heal_log_recent": self._heal_log[-10:],
        }


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[SelfHealingEngine] = None


def get_self_healing_engine() -> SelfHealingEngine:
    global _instance
    if _instance is None:
        _instance = SelfHealingEngine()
    return _instance


# ─────────────────────────────────────────────────────────────────────────────
#  BACKWARD COMPATIBILITY — merged from error_recovery.py
#  These classes allow old imports to keep working:
#    from app.core.self_healing import ErrorHandler, RecoveryAction, RecoveryStrategy
# ─────────────────────────────────────────────────────────────────────────────

from enum import Enum


class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryStrategy(Enum):
    RETRY = "retry"
    FALLBACK = "fallback"
    CIRCUIT_BREAK = "circuit_break"
    GRACEFUL_DEGRADE = "graceful_degrade"
    ABORT = "abort"


@dataclass
class RecoveryAction:
    name: str
    strategy: RecoveryStrategy
    handler: Callable
    max_retries: int = 3
    backoff_factor: float = 2.0
    timeout: int = 30
    fallback_handler: Optional[Callable] = None


class ErrorHandler:
    """
    Backward-compatible wrapper around SelfHealingEngine.
    Delegates to the singleton healer for error tracking & recovery.
    """

    def __init__(self):
        self._engine = get_self_healing_engine()
        self.recovery_actions: Dict[str, RecoveryAction] = {}
        self.error_stats = {
            "total_errors": 0,
            "recovered": 0,
            "recovery_rate": 0,
            "by_severity": {},
        }

    def register_recovery_action(self, error_type: str, action: RecoveryAction):
        self.recovery_actions[error_type] = action

    async def handle_error(self, error: Exception, context_data: Dict[str, Any] = None) -> bool:
        context_data = context_data or {}
        module = context_data.get("operation", "unknown")
        self._engine.capture_error(error, module=module, context=str(context_data)[:200])
        self.error_stats["total_errors"] += 1

        error_type = type(error).__name__
        if error_type in self.recovery_actions:
            action = self.recovery_actions[error_type]
            if action.strategy == RecoveryStrategy.RETRY:
                for attempt in range(action.max_retries):
                    try:
                        wait = action.backoff_factor ** attempt
                        await asyncio.sleep(wait)
                        await asyncio.wait_for(action.handler(), timeout=action.timeout)
                        self.error_stats["recovered"] += 1
                        self._update_rate()
                        return True
                    except Exception:
                        continue
            elif action.strategy == RecoveryStrategy.FALLBACK and action.fallback_handler:
                try:
                    await asyncio.wait_for(action.fallback_handler(), timeout=action.timeout)
                    self.error_stats["recovered"] += 1
                    self._update_rate()
                    return True
                except Exception:
                    pass
            elif action.strategy == RecoveryStrategy.GRACEFUL_DEGRADE:
                self.error_stats["recovered"] += 1
                self._update_rate()
                return True

        return False

    def _update_rate(self):
        total = self.error_stats["total_errors"]
        if total > 0:
            self.error_stats["recovery_rate"] = round(self.error_stats["recovered"] / total * 100, 1)

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self.error_stats,
            "healer_stats": self._engine.get_stats(),
            "circuit_breakers": {
                name: cb["state"] for name, cb in self._engine._circuit_breakers.items()
            },
        }

    def get_error_history(self, limit: int = 50) -> List[dict]:
        return self._engine.get_error_history(limit)

