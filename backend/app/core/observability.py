"""
Igris Observability — Request tracing, correlation IDs, structured logging context.
Provides: ContextVar request IDs, span tracking, structured log enrichment.
"""
from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from collections import deque
from threading import RLock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Request ID Context ────────────────────────────────────────────────────────

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def new_request_id() -> str:
    return str(uuid.uuid4())


def set_request_id(rid: str) -> contextvars.Token[str]:
    return request_id_ctx.set(rid)


def get_request_id() -> str:
    return request_id_ctx.get() or "-"


def reset_request_id(token: contextvars.Token[str]) -> None:
    request_id_ctx.reset(token)


# ── Span / Trace ──────────────────────────────────────────────────────────────

class Span:
    """A single execution span within a trace."""

    def __init__(self, name: str, trace_id: str, parent_id: str = ""):
        self.span_id  = uuid.uuid4().hex[:12]
        self.trace_id = trace_id
        self.parent_id = parent_id
        self.name     = name
        self.start_ts = time.perf_counter()
        self.wall_ts  = time.time()
        self.end_ts: Optional[float] = None
        self.tags: Dict[str, Any] = {}
        self.events: List[dict] = []
        self.error: Optional[str] = None

    def set_tag(self, key: str, value: Any) -> "Span":
        self.tags[key] = value
        return self

    def add_event(self, name: str, attrs: Dict = None) -> "Span":
        self.events.append({"name": name, "ts": time.time(), "attrs": attrs or {}})
        return self

    def finish(self, error: str = None) -> float:
        self.end_ts = time.perf_counter()
        self.error = error
        return self.duration_ms

    @property
    def duration_ms(self) -> float:
        end = self.end_ts or time.perf_counter()
        return round((end - self.start_ts) * 1000, 2)

    def to_dict(self) -> dict:
        return {
            "span_id":    self.span_id,
            "trace_id":   self.trace_id,
            "parent_id":  self.parent_id,
            "name":       self.name,
            "start_wall": self.wall_ts,
            "duration_ms": self.duration_ms,
            "tags":       self.tags,
            "events":     self.events,
            "error":      self.error,
            "finished":   self.end_ts is not None,
        }


class Tracer:
    """In-process distributed tracer. Keeps last N traces in memory."""

    MAX_TRACES = 200

    def __init__(self) -> None:
        self._traces: Dict[str, List[Span]] = {}
        self._finished: deque = deque(maxlen=self.MAX_TRACES)
        self._lock = RLock()

    def start_trace(self, name: str) -> Span:
        """Start a new root span (new trace)."""
        trace_id = uuid.uuid4().hex[:16]
        span = Span(name, trace_id)
        with self._lock:
            self._traces[trace_id] = [span]
        return span

    def start_span(self, name: str, parent: Span) -> Span:
        """Start a child span within an existing trace."""
        span = Span(name, parent.trace_id, parent_id=parent.span_id)
        with self._lock:
            self._traces.setdefault(parent.trace_id, []).append(span)
        return span

    def finish_trace(self, root_span: Span) -> dict:
        """Finish and archive a trace. Returns summary."""
        root_span.finish()
        trace_id = root_span.trace_id
        with self._lock:
            spans = self._traces.pop(trace_id, [root_span])
        # Finish any unfinished spans
        for s in spans:
            if s.end_ts is None:
                s.finish()
        summary = {
            "trace_id":    trace_id,
            "root_name":   root_span.name,
            "total_ms":    root_span.duration_ms,
            "span_count":  len(spans),
            "errors":      [s.error for s in spans if s.error],
            "spans":       [s.to_dict() for s in spans],
        }
        self._finished.append(summary)
        return summary

    def get_recent_traces(self, limit: int = 20) -> List[dict]:
        with self._lock:
            return list(self._finished)[-limit:]

    def get_stats(self) -> dict:
        traces = list(self._finished)
        if not traces:
            return {"total_traces": 0}
        durations = [t["total_ms"] for t in traces]
        errors = sum(1 for t in traces if t["errors"])
        return {
            "total_traces":    len(traces),
            "traces_with_errors": errors,
            "avg_duration_ms": round(sum(durations) / len(durations), 2),
            "max_duration_ms": round(max(durations), 2),
            "min_duration_ms": round(min(durations), 2),
        }


# ── Structured Log Filter ─────────────────────────────────────────────────────

class RequestIdFilter(logging.Filter):
    """Inject request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


# ── Request Metrics Tracker ───────────────────────────────────────────────────

class RequestMetrics:
    """Track per-endpoint latency and status code counts."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._endpoints: Dict[str, dict] = {}

    def record(self, method: str, path: str, status: int, duration_ms: float) -> None:
        key = f"{method} {path}"
        with self._lock:
            if key not in self._endpoints:
                self._endpoints[key] = {
                    "count": 0, "errors": 0,
                    "total_ms": 0.0, "max_ms": 0.0,
                    "status_codes": {}
                }
            ep = self._endpoints[key]
            ep["count"] += 1
            ep["total_ms"] += duration_ms
            ep["max_ms"] = max(ep["max_ms"], duration_ms)
            if status >= 400:
                ep["errors"] += 1
            ep["status_codes"][str(status)] = ep["status_codes"].get(str(status), 0) + 1

    def get_summary(self) -> List[dict]:
        with self._lock:
            result = []
            for endpoint, data in self._endpoints.items():
                count = data["count"]
                result.append({
                    "endpoint":    endpoint,
                    "requests":    count,
                    "errors":      data["errors"],
                    "error_rate":  round(data["errors"] / count * 100, 1) if count else 0,
                    "avg_ms":      round(data["total_ms"] / count, 2) if count else 0,
                    "max_ms":      round(data["max_ms"], 2),
                    "status_codes": data["status_codes"],
                })
            return sorted(result, key=lambda x: x["requests"], reverse=True)


# ── Singletons ────────────────────────────────────────────────────────────────

tracer = Tracer()
request_metrics = RequestMetrics()
