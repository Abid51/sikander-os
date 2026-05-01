"""
Fallback Error Handler — Full implementation
Provides structured recovery actions, error classification, and audit trail.
"""
from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorSeverity:
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class FallbackErrorHandler:
    """
    Full-featured fallback error handler for Igris OS.

    Provides:
    - Error classification by type/severity
    - Structured recovery action recommendations
    - Audit trail of recent errors (last 500)
    - Circuit-breaker style consecutive-failure tracking
    - Component-level failure counters
    """

    MAX_AUDIT_ENTRIES = 500

    def __init__(self) -> None:
        self._audit_log: List[Dict] = []
        self._component_failures: Dict[str, int] = {}
        self._component_last_error: Dict[str, str] = {}
        self._total_errors = 0
        self._recovered = 0

    # ── Classification ─────────────────────────────────────────────────────────

    def _classify_error(self, error: Exception) -> tuple[str, str]:
        """Classify error by type and return (error_type, severity)"""
        err_str = str(error).lower()
        err_class = type(error).__name__

        if isinstance(error, (ConnectionError, ConnectionRefusedError, TimeoutError)):
            return "network", ErrorSeverity.HIGH
        if isinstance(error, (FileNotFoundError, PermissionError, OSError)):
            return "filesystem", ErrorSeverity.MEDIUM
        if isinstance(error, (MemoryError,)):
            return "memory", ErrorSeverity.CRITICAL
        if isinstance(error, (ImportError, ModuleNotFoundError)):
            return "dependency", ErrorSeverity.MEDIUM
        if isinstance(error, (ValueError, TypeError, KeyError, AttributeError)):
            return "validation", ErrorSeverity.LOW
        if isinstance(error, (RuntimeError,)):
            return "runtime", ErrorSeverity.HIGH
        if "database" in err_str or "sql" in err_str or "sqlite" in err_str:
            return "database", ErrorSeverity.HIGH
        if "api" in err_str or "http" in err_str or "status" in err_str:
            return "api", ErrorSeverity.MEDIUM
        if "llm" in err_str or "openai" in err_str or "ollama" in err_str:
            return "llm", ErrorSeverity.MEDIUM
        if "auth" in err_str or "token" in err_str or "permission" in err_str:
            return "auth", ErrorSeverity.HIGH
        return "unknown", ErrorSeverity.MEDIUM

    def _get_recovery_actions(self, error_type: str, severity: str, context: dict) -> List[str]:
        """Return ordered list of recommended recovery actions"""
        base_actions = {
            "network": [
                "Check internet/network connectivity",
                "Verify target host is reachable",
                "Retry with exponential backoff",
                "Switch to backup/fallback provider",
                "Use cached responses if available"
            ],
            "filesystem": [
                "Verify file path exists",
                "Check read/write permissions",
                "Ensure disk space is available",
                "Create missing directories",
                "Log file operation to audit trail"
            ],
            "memory": [
                "Free memory by clearing caches",
                "Restart affected daemon",
                "Reduce batch sizes",
                "Alert administrator immediately"
            ],
            "dependency": [
                f"Run: pip install {context.get('module', '<module>')}",
                "Check requirements.txt is up to date",
                "Verify virtual environment activation",
                "Use graceful fallback if optional dependency"
            ],
            "validation": [
                "Log invalid input for debugging",
                "Return structured error to caller",
                "Use default value if safe",
                "Validate inputs at entry point"
            ],
            "runtime": [
                "Check system logs for context",
                "Restart affected daemon/service",
                "Reduce load on affected component",
                "Enable verbose logging"
            ],
            "database": [
                "Check database file integrity",
                "Retry transaction",
                "Run database VACUUM if SQLite",
                "Use in-memory fallback temporarily"
            ],
            "api": [
                "Check API key configuration",
                "Verify rate limit status",
                "Retry after delay",
                "Switch to alternative provider"
            ],
            "llm": [
                "Verify Ollama is running (ollama serve)",
                "Check LLM model is pulled",
                "Fallback to smaller/faster model",
                "Use cached response if available",
                "Switch provider in /llm/config"
            ],
            "auth": [
                "Verify IGRIS_API_TOKEN is set in .env",
                "Check token has not expired",
                "Re-authenticate and update token",
                "Revoke and regenerate if compromised"
            ],
            "unknown": [
                "Check system logs for full traceback",
                "Restart affected component",
                "Report bug if issue persists"
            ]
        }
        actions = base_actions.get(error_type, base_actions["unknown"])

        # Prepend critical action if needed
        if severity == ErrorSeverity.CRITICAL:
            actions = ["⚠️ CRITICAL: Alert administrator immediately"] + actions

        return actions

    # ── Main Handle ────────────────────────────────────────────────────────────

    def handle_error(
        self,
        error: Exception,
        context: Any = None,
        component: str = "unknown"
    ) -> Dict:
        """
        Handle an error with full classification, recovery recommendations,
        and audit trail recording.
        """
        self._total_errors += 1
        self._component_failures[component] = self._component_failures.get(component, 0) + 1

        error_type, severity = self._classify_error(error)
        ctx_dict = context if isinstance(context, dict) else {"raw_context": str(context)}
        recovery_actions = self._get_recovery_actions(error_type, severity, ctx_dict)

        # Capture traceback safely
        tb = ""
        try:
            tb = traceback.format_exc()
            if "NoneType: None" in tb:
                tb = ""
        except Exception:
            pass

        timestamp = datetime.now().isoformat()
        error_id = f"err_{int(time.time()*1000)}"

        record = {
            "error_id": error_id,
            "timestamp": timestamp,
            "component": component,
            "error_type": error_type,
            "severity": severity,
            "error_class": type(error).__name__,
            "message": str(error)[:500],
            "traceback": tb[:2000] if tb else "",
            "context": str(context)[:300] if context else "",
            "recovery_actions": recovery_actions,
            "consecutive_failures": self._component_failures.get(component, 1),
            "status": "handled",
            # Test / UX aliases
            "recovery_action": f"basic_error_logging; {error_type}; primary: {recovery_actions[0]}",
            "next_steps":      "\n".join(recovery_actions),
        }

        self._component_last_error[component] = error_id
        self._audit_log.append(record)
        if len(self._audit_log) > self.MAX_AUDIT_ENTRIES:
            self._audit_log.pop(0)

        # Log appropriately
        log_msg = f"[FALLBACK] [{severity.upper()}] {type(error).__name__} in '{component}': {str(error)[:200]}"
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(log_msg)
        elif severity == ErrorSeverity.HIGH:
            logger.error(log_msg)
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return record

    def mark_recovered(self, component: str) -> None:
        """Mark a component as recovered — resets failure counter"""
        self._component_failures[component] = 0
        self._recovered += 1
        logger.info(f"[FALLBACK] Component '{component}' recovered.")

    # ── Queries ────────────────────────────────────────────────────────────────

    def get_recent_errors(self, limit: int = 20, component: str = None) -> List[Dict]:
        """Get recent errors, optionally filtered by component"""
        errors = self._audit_log
        if component:
            errors = [e for e in errors if e.get("component") == component]
        return errors[-limit:]

    def get_component_health(self) -> Dict:
        """Return health summary per component"""
        health = {}
        for comp, failures in self._component_failures.items():
            health[comp] = {
                "consecutive_failures": failures,
                "status": "critical" if failures >= 10 else
                          "degraded" if failures >= 3 else
                          "healthy" if failures == 0 else "warning",
                "last_error_id": self._component_last_error.get(comp)
            }
        return health

    def get_stats(self) -> Dict:
        """Get overall error handler statistics"""
        severity_counts: Dict[str, int] = {}
        type_counts: Dict[str, int] = {}
        for e in self._audit_log:
            s = e.get("severity", "unknown")
            t = e.get("error_type", "unknown")
            severity_counts[s] = severity_counts.get(s, 0) + 1
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_errors": self._total_errors,
            "recovered": self._recovered,
            "audit_log_size": len(self._audit_log),
            "by_severity": severity_counts,
            "by_type": type_counts,
            "component_failures": dict(self._component_failures),
            "component_health": self.get_component_health()
        }

    def clear_audit_log(self) -> Dict:
        """Clear the audit log"""
        count = len(self._audit_log)
        self._audit_log.clear()
        return {"cleared": count}


# Global singleton
fallback_handler = FallbackErrorHandler()