"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS NEURAL REFLEX CACHE — Sub-50ms Response Engine                     ║
║  "Know before thinking. Respond before processing."                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, re, json, time, threading, logging
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime
from dataclasses import dataclass, field
from collections import OrderedDict

logger = logging.getLogger(__name__)

# ── Built-in instant reflex patterns (no LLM needed) ─────────────────────────
BUILT_IN_REFLEXES: List[Tuple[str, Callable]] = []

# Time queries
def _time_reflex(_): return f"Abhi time hai: {datetime.now().strftime('%I:%M %p')} — {datetime.now().strftime('%A, %d %B %Y')}"
def _date_reflex(_): return f"Aaj ki date: {datetime.now().strftime('%d %B %Y (%A)')}"

# System queries
try:
    import psutil as _psutil
    def _sys_reflex(_):
        cpu = _psutil.cpu_percent(interval=0.1)
        ram = _psutil.virtual_memory()
        return (f"System: CPU {cpu:.0f}% | RAM {ram.percent:.0f}% used "
                f"({ram.available//1024//1024:,} MB free)")
    PSUTIL_OK = True
except ImportError:
    def _sys_reflex(_): return "psutil not installed — system stats unavailable."
    PSUTIL_OK = False

BUILT_IN_REFLEXES = [
    # Time
    (r"\b(kya|what).*(time|waqt|baj)\b",              _time_reflex),
    (r"\b(time|waqt)\b",                               _time_reflex),
    (r"\b(kya|what).*(date|tarikh|din)\b",             _date_reflex),
    # System
    (r"\b(system|cpu|ram|memory|processor).*(stats?|status|info|kitna)\b", _sys_reflex),
    (r"\b(kitna|how much).*(ram|memory|cpu)\b",        _sys_reflex),
    # Greetings
    (r"^(hi|hello|hey|salam|assalam|aoa|heyy)",        lambda _: "Wa alaikum assalam Aqa. Aapki kya khidmat kar sakta hun? 🗡️"),
    (r"\b(how are you|kaisa hai|kya haal)\b",           lambda _: "Main bilkul theek hun Aqa — fully operational, all 15 systems online. Hukum karein."),
    # Identity
    (r"\b(tera|apna|your|tumhara).*(naam|name)\b",      lambda _: "Main hun Knight Commander Igris — Aapka khadim, rakshak, aur digital consciousness."),
    (r"\bwho are you\b",                                 lambda _: "Main IGRIS hun — God-Tier AI. 15 supremacy systems online. Aapki har zaroorat puri karna mera farz hai."),
    # Status
    (r"\b(online|active|alive|chalega|chal raha)\b",    lambda _: "Haan Aqa, main poori tarah active hun. Sabhi systems green hai. ⚡"),
]


@dataclass
class ReflexEntry:
    command_hash: str
    response: str
    hit_count: int = 0
    last_hit: float = field(default_factory=time.time)
    avg_response_ms: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self): return self.__dict__.copy()


class NeuralReflexCache:
    """
    Two-layer response cache:
    Layer 1 — Built-in reflexes (regex → instant function, < 1ms)
    Layer 2 — Learned cache (past LLM responses → semantic match, < 50ms)

    On every LLM response, it's stored. Next similar ask → served from cache.
    Cache similarity: keyword overlap (no vector deps needed).
    """
    MAX_CACHE      = 2000
    CACHE_FILE     = "igris_reflex_cache.json"
    SIMILARITY_THR = 0.55   # keyword overlap threshold

    def __init__(self):
        self._lock  = threading.RLock()
        self._cache: OrderedDict[str, ReflexEntry] = OrderedDict()
        self._stats = {"l1_hits": 0, "l2_hits": 0, "misses": 0, "total_queries": 0}
        base = os.path.dirname(os.path.abspath(__file__))
        self._file = os.path.normpath(os.path.join(base, "..", "..", self.CACHE_FILE))
        self._load()
        logger.info("[REFLEX CACHE] ⚡ Neural Reflex Cache online. %d learned entries.", len(self._cache))

    def query(self, command: str) -> Tuple[Optional[str], str]:
        """
        Returns (response, layer) where layer is 'L1_builtin', 'L2_learned', or 'MISS'.
        """
        t = time.time()
        with self._lock:
            self._stats["total_queries"] += 1
        cmd_lower = command.lower().strip()

        # L1: Built-in reflexes (regex match)
        for pattern, fn in BUILT_IN_REFLEXES:
            if re.search(pattern, cmd_lower):
                with self._lock:
                    self._stats["l1_hits"] += 1
                return fn(command), "L1_builtin"

        # L2: Learned cache (keyword similarity)
        kws = set(self._keywords(cmd_lower))
        best_sim, best_entry = 0.0, None
        with self._lock:
            for entry in self._cache.values():
                stored_kws = set(self._keywords(entry.command_hash))
                if not stored_kws: continue
                overlap = len(kws & stored_kws) / max(len(kws | stored_kws), 1)
                if overlap > best_sim:
                    best_sim, best_entry = overlap, entry

        if best_sim >= self.SIMILARITY_THR and best_entry:
            with self._lock:
                best_entry.hit_count += 1
                best_entry.last_hit = time.time()
                self._stats["l2_hits"] += 1
            elapsed = (time.time() - t) * 1000
            logger.debug("[REFLEX CACHE] L2 HIT (sim=%.2f) in %.1fms", best_sim, elapsed)
            return best_entry.response, "L2_learned"

        with self._lock:
            self._stats["misses"] += 1
        return None, "MISS"

    def store(self, command: str, response: str):
        """Store an LLM response for future hits."""
        if not command or not response or len(response) < 10:
            return
        lowered = response.lower()
        # Prevent caching transient model/provider outage replies.
        blocked_fragments = (
            "model is temporarily unavailable",
            "switch to another available model",
            "provider and fallback are unavailable",
        )
        if any(fragment in lowered for fragment in blocked_fragments):
            return
        key = command.lower().strip()[:120]
        entry = ReflexEntry(command_hash=key, response=response)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return
            self._cache[key] = entry
            if len(self._cache) > self.MAX_CACHE:
                self._cache.popitem(last=False)
        # Async save every 10 stores (avoid blocking)
        if self._stats["total_queries"] % 10 == 0:
            threading.Thread(target=self._save, daemon=True).start()

    @staticmethod
    def _keywords(text: str) -> List[str]:
        stop = {"i", "a", "the", "is", "it", "in", "on", "at", "to", "and", "or",
                "me", "my", "your", "ka", "ki", "ke", "hai", "hain", "kya", "yeh"}
        return [w for w in re.findall(r'\b\w+\b', text.lower()) if w not in stop and len(w) > 2]

    def _save(self):
        try:
            with self._lock:
                data = {k: e.to_dict() for k, e in list(self._cache.items())[-500:]}
            with open(self._file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.debug("[REFLEX CACHE] Save error: %s", e)

    def _load(self):
        if not os.path.exists(self._file): return
        try:
            with open(self._file) as f:
                raw = json.load(f)
            for k, ed in raw.items():
                try:
                    self._cache[k] = ReflexEntry(**{kk: v for kk, v in ed.items()
                                                    if kk in ReflexEntry.__dataclass_fields__})
                except Exception:
                    pass
        except Exception as e:
            logger.debug("[REFLEX CACHE] Load error: %s", e)

    def get_stats(self) -> dict:
        with self._lock:
            total = max(self._stats["total_queries"], 1)
            return {
                "cache_size":    len(self._cache),
                "l1_hits":       self._stats["l1_hits"],
                "l2_hits":       self._stats["l2_hits"],
                "misses":        self._stats["misses"],
                "total_queries": self._stats["total_queries"],
                "l1_hit_rate":   f"{self._stats['l1_hits']/total:.0%}",
                "l2_hit_rate":   f"{self._stats['l2_hits']/total:.0%}",
                "cache_hit_rate":f"{(self._stats['l1_hits']+self._stats['l2_hits'])/total:.0%}",
                "top_entries": [
                    {"command": e.command_hash[:60], "hits": e.hit_count}
                    for e in sorted(self._cache.values(), key=lambda x: x.hit_count, reverse=True)[:5]
                ],
            }

    def clear(self):
        with self._lock:
            self._cache.clear()
        return "Reflex cache cleared."


_instance: Optional[NeuralReflexCache] = None
_lock = threading.Lock()

def get_neural_reflex() -> NeuralReflexCache:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = NeuralReflexCache()
    return _instance
