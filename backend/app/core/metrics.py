"""
Igris Metrics — Production-grade in-process metrics store.
Thread-safe counters, gauges, histograms, and timers.
No external dependencies (no Prometheus, no Redis).
"""
from __future__ import annotations

import time
import threading
from collections import defaultdict, deque
from typing import Any, Callable, Dict, List, Optional


_lock = threading.RLock()

# ── Storage ───────────────────────────────────────────────────────────────────
_counts:    Dict[str, int]   = defaultdict(int)      # inc/dec counters
_gauges:    Dict[str, float] = {}                    # set/get absolute values
_histograms: Dict[str, deque] = {}                   # sliding windows of values
_timers:    Dict[str, List[float]] = {}              # durations in seconds


# ── Counters ──────────────────────────────────────────────────────────────────

def inc(name: str, delta: int = 1, tags: Dict[str, str] = None) -> None:
    """Increment a named counter."""
    key = _tag_key(name, tags)
    with _lock:
        _counts[key] += delta


def dec(name: str, delta: int = 1, tags: Dict[str, str] = None) -> None:
    """Decrement a named counter."""
    key = _tag_key(name, tags)
    with _lock:
        _counts[key] -= delta


def get_count(name: str, tags: Dict[str, str] = None) -> int:
    with _lock:
        return _counts.get(_tag_key(name, tags), 0)


# ── Gauges ────────────────────────────────────────────────────────────────────

def set_gauge(name: str, value: float, tags: Dict[str, str] = None) -> None:
    """Set a gauge (absolute value metric, e.g. CPU%)."""
    key = _tag_key(name, tags)
    with _lock:
        _gauges[key] = value


def get_gauge(name: str, tags: Dict[str, str] = None) -> Optional[float]:
    with _lock:
        return _gauges.get(_tag_key(name, tags))


# ── Histograms ────────────────────────────────────────────────────────────────

def record(name: str, value: float, window: int = 1000, tags: Dict[str, str] = None) -> None:
    """Record a value in a sliding-window histogram."""
    key = _tag_key(name, tags)
    with _lock:
        if key not in _histograms:
            _histograms[key] = deque(maxlen=window)
        _histograms[key].append(value)


def get_histogram(name: str, tags: Dict[str, str] = None) -> Dict[str, Any]:
    """Return percentile stats for a histogram."""
    key = _tag_key(name, tags)
    with _lock:
        data = list(_histograms.get(key, []))
    if not data:
        return {"count": 0}
    data_sorted = sorted(data)
    n = len(data_sorted)
    return {
        "count": n,
        "min":   round(data_sorted[0], 4),
        "max":   round(data_sorted[-1], 4),
        "mean":  round(sum(data_sorted) / n, 4),
        "p50":   round(data_sorted[int(n * 0.50)], 4),
        "p90":   round(data_sorted[int(n * 0.90)], 4),
        "p99":   round(data_sorted[min(int(n * 0.99), n - 1)], 4),
    }


# ── Timers ────────────────────────────────────────────────────────────────────

def time_it(name: str, tags: Dict[str, str] = None):
    """Context manager / decorator to time a block or function call."""
    return _Timer(name, tags)


class _Timer:
    def __init__(self, name: str, tags: Optional[Dict[str, str]]):
        self._name = name
        self._tags = tags
        self._start: float = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_):
        elapsed = time.perf_counter() - self._start
        record(self._name, elapsed, tags=self._tags)
        key = _tag_key(self._name, self._tags)
        with _lock:
            if key not in _timers:
                _timers[key] = []
            _timers[key].append(elapsed)
            if len(_timers[key]) > 500:
                _timers[key].pop(0)

    def __call__(self, fn: Callable) -> Callable:
        """Use as decorator."""
        import functools

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with self.__class__(self._name, self._tags):
                return fn(*args, **kwargs)

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            with self.__class__(self._name, self._tags):
                return await fn(*args, **kwargs)

        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(fn) else wrapper


# ── Full Snapshot ─────────────────────────────────────────────────────────────

def snapshot() -> Dict[str, Any]:
    """Return a complete snapshot of all metrics — safe for API exposure."""
    with _lock:
        counts_copy    = dict(_counts)
        gauges_copy    = dict(_gauges)
        histo_keys     = list(_histograms.keys())
        timer_keys     = list(_timers.keys())

    histo_stats = {k: get_histogram(k) for k in histo_keys}
    timer_stats = {}
    for k in timer_keys:
        with _lock:
            vals = list(_timers.get(k, []))
        if vals:
            vals_s = sorted(vals)
            n = len(vals_s)
            timer_stats[k] = {
                "calls": n,
                "mean_ms": round(sum(vals_s) / n * 1000, 2),
                "p95_ms":  round(vals_s[min(int(n * 0.95), n - 1)] * 1000, 2),
                "max_ms":  round(vals_s[-1] * 1000, 2),
            }

    out = {
        "counters":   counts_copy,
        "gauges":     gauges_copy,
        "histograms": histo_stats,
        "timers":     timer_stats,
    }
    # Flat counter aliases (tests and simple dashboards use snapshot()["name"])
    out.update(counts_copy)
    return out


def reset() -> None:
    """Clear all metrics — useful for tests."""
    with _lock:
        _counts.clear()
        _gauges.clear()
        _histograms.clear()
        _timers.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tag_key(name: str, tags: Optional[Dict[str, str]]) -> str:
    if not tags:
        return name
    tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
    return f"{name}{{{tag_str}}}"
