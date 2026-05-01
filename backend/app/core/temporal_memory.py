"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS TEMPORAL MEMORY ARCHITECTURE                                        ║
║  "Five layers of memory — just like a human mind."                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, json, time, threading, logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class MemoryLayer(str, Enum):
    WORKING   = "working"    # Last 5 minutes — ultra-fast RAM
    SHORT     = "short"      # Last 7 days — decays
    LONG      = "long"       # Permanent (high-importance facts)
    EPISODIC  = "episodic"   # Events + emotions tied together
    SEMANTIC  = "semantic"   # Pure facts, no emotion


@dataclass
class MemoryTrace:
    trace_id: str
    layer: MemoryLayer
    content: str
    emotion: str = ""
    importance: float = 0.5    # 0-1
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    decay_factor: float = 1.0  # multiplied per day (SHORT layer)
    tags: List[str] = field(default_factory=list)

    @property
    def age_days(self) -> float:
        return (time.time() - self.created_at) / 86400

    @property
    def effective_strength(self) -> float:
        if self.layer == MemoryLayer.WORKING:
            # Decays in minutes
            age_min = (time.time() - self.created_at) / 60
            return max(0, 1.0 - age_min / 5)
        elif self.layer == MemoryLayer.SHORT:
            return max(0, self.decay_factor ** self.age_days) * self.importance
        elif self.layer == MemoryLayer.LONG:
            return self.importance  # No decay
        elif self.layer == MemoryLayer.EPISODIC:
            # Emotion strengthens over time (emotional memories persist)
            emotion_boost = 0.3 if self.emotion else 0
            return min(1.0, self.importance + emotion_boost)
        else:  # SEMANTIC
            return 0.9  # Almost permanent facts

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["layer"] = self.layer.value
        d["effective_strength"] = round(self.effective_strength, 3)
        d["age_days"] = round(self.age_days, 2)
        return d


IMPORTANCE_KEYWORDS = {
    "high": ["deadline", "urgent", "critical", "important", "never forget",
             "remember", "deadline", "birthday", "password", "key", "secret"],
    "episodic": ["angry", "frustrated", "happy", "excited", "sad", "stressed",
                 "amazing", "terrible", "love", "hate", "feel", "emotion"],
    "semantic": ["fact", "definition", "means", "is a", "are", "wikipedia",
                 "according to", "study shows", "research"],
}


class TemporalMemory:
    """
    Five-layer memory system mimicking human cognition.
    Automatically classifies and stores memories in the appropriate layer.
    Decays working/short-term, preserves long-term/episodic/semantic.
    """
    DATA_FILE = "igris_temporal_memory.json"
    DECAY_INTERVAL = 3600   # Run decay every hour

    def __init__(self):
        self._lock = threading.RLock()
        self._layers: Dict[MemoryLayer, List[MemoryTrace]] = {
            layer: [] for layer in MemoryLayer
        }
        self._trace_counter = 0

        base = os.path.dirname(os.path.abspath(__file__))
        self._file = os.path.normpath(os.path.join(base, "..", "..", self.DATA_FILE))
        self._load()
        threading.Thread(target=self._decay_loop, daemon=True).start()
        logger.info("[TEMPORAL MEMORY] 🧠 5-Layer Temporal Memory online.")

    # ─────────────────────────────────────────────────────────────────────
    # STORE
    # ─────────────────────────────────────────────────────────────────────

    def store(self, content: str, emotion: str = "", tags: List[str] = None,
              force_layer: MemoryLayer = None) -> str:
        """Auto-classify and store a memory trace."""
        layer = force_layer or self._classify(content, emotion)
        importance = self._compute_importance(content, layer)

        with self._lock:
            self._trace_counter += 1
            trace_id = f"tm_{self._trace_counter}_{int(time.time())}"

        trace = MemoryTrace(
            trace_id=trace_id,
            layer=layer,
            content=content[:300],
            emotion=emotion,
            importance=importance,
            tags=tags or [],
        )

        with self._lock:
            self._layers[layer].append(trace)
            # Cap layer sizes
            caps = {MemoryLayer.WORKING: 20, MemoryLayer.SHORT: 200,
                    MemoryLayer.LONG: 1000, MemoryLayer.EPISODIC: 500,
                    MemoryLayer.SEMANTIC: 2000}
            layer_list = self._layers[layer]
            cap = caps.get(layer, 500)
            if len(layer_list) > cap:
                # Remove weakest
                self._layers[layer] = sorted(
                    layer_list, key=lambda t: t.effective_strength)[-cap:]

        logger.debug("[TEMPORAL MEMORY] Stored [%s] → %s: %s...",
                     layer.value, trace_id, content[:40])
        return trace_id

    def _classify(self, content: str, emotion: str) -> MemoryLayer:
        """Auto-classify content into the correct memory layer."""
        c = content.lower()
        # Working: Very recent commands
        # Episodic: Has emotion
        if emotion or any(w in c for w in IMPORTANCE_KEYWORDS["episodic"]):
            return MemoryLayer.EPISODIC
        # Semantic: Facts/definitions
        if any(w in c for w in IMPORTANCE_KEYWORDS["semantic"]):
            return MemoryLayer.SEMANTIC
        # Long: High importance keywords
        if any(w in c for w in IMPORTANCE_KEYWORDS["high"]):
            return MemoryLayer.LONG
        # Default: Short-term
        return MemoryLayer.SHORT

    def _compute_importance(self, content: str, layer: MemoryLayer) -> float:
        c = content.lower()
        score = 0.5
        if any(w in c for w in IMPORTANCE_KEYWORDS["high"]):
            score += 0.3
        if len(content) > 100:
            score += 0.1
        if layer == MemoryLayer.LONG:
            score = max(score, 0.8)
        return min(1.0, score)

    # ─────────────────────────────────────────────────────────────────────
    # RECALL
    # ─────────────────────────────────────────────────────────────────────

    def recall(self, query: str, top_k: int = 5,
               layers: List[MemoryLayer] = None) -> List[MemoryTrace]:
        """Retrieve relevant memories across specified layers."""
        q_words = set(query.lower().split())
        results: List[Tuple[float, MemoryTrace]] = []

        target_layers = layers or list(MemoryLayer)
        with self._lock:
            for layer in target_layers:
                for trace in self._layers[layer]:
                    if trace.effective_strength < 0.01:
                        continue
                    # Simple keyword overlap
                    t_words = set(trace.content.lower().split())
                    overlap = len(q_words & t_words) / max(len(q_words | t_words), 1)
                    tag_bonus = 0.2 if any(t in query.lower() for t in trace.tags) else 0
                    score = overlap * trace.effective_strength + tag_bonus
                    if score > 0.05:
                        results.append((score, trace))

        results.sort(key=lambda x: -x[0])
        top = [t for _, t in results[:top_k]]

        # Update access
        with self._lock:
            for trace in top:
                trace.last_accessed = time.time()
                trace.access_count += 1

        return top

    def promote_to_long_term(self, trace_id: str) -> str:
        """Manually promote a short-term memory to long-term."""
        with self._lock:
            for layer in MemoryLayer:
                for trace in self._layers[layer]:
                    if trace.trace_id == trace_id:
                        self._layers[layer].remove(trace)
                        trace.layer = MemoryLayer.LONG
                        trace.importance = max(trace.importance, 0.8)
                        self._layers[MemoryLayer.LONG].append(trace)
                        return f"Promoted {trace_id} to LONG-TERM memory."
        return "Trace not found."

    # ─────────────────────────────────────────────────────────────────────
    # DECAY
    # ─────────────────────────────────────────────────────────────────────

    def _decay_loop(self):
        while True:
            time.sleep(self.DECAY_INTERVAL)
            try:
                self._run_decay()
                self._save()
            except Exception as e:
                logger.debug("[TEMPORAL MEMORY] Decay error: %s", e)

    def _run_decay(self):
        """Remove dead memories from working and short-term layers."""
        removed = 0
        with self._lock:
            for layer in [MemoryLayer.WORKING, MemoryLayer.SHORT]:
                before = len(self._layers[layer])
                self._layers[layer] = [t for t in self._layers[layer]
                                       if t.effective_strength > 0.05]
                removed += before - len(self._layers[layer])
        logger.debug("[TEMPORAL MEMORY] Decay removed %d expired traces.", removed)

    # ─────────────────────────────────────────────────────────────────────
    # PROMPT INJECTION
    # ─────────────────────────────────────────────────────────────────────

    def to_prompt_context(self, query: str) -> str:
        memories = self.recall(query, top_k=4)
        if not memories:
            return ""
        lines = []
        for m in memories:
            emotion_part = f" [Emotion: {m.emotion}]" if m.emotion else ""
            lines.append(f"  [{m.layer.value.upper()}]{emotion_part} {m.content[:100]}")
        return "\n[TEMPORAL MEMORY — Relevant Past]:\n" + "\n".join(lines) + "\n"

    # ─────────────────────────────────────────────────────────────────────
    # PERSISTENCE & STATS
    # ─────────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        with self._lock:
            total = sum(len(v) for v in self._layers.values())
            return {
                "total_traces": total,
                "by_layer": {layer.value: len(self._layers[layer]) for layer in MemoryLayer},
                "trace_counter": self._trace_counter,
            }

    def get_layer(self, layer_name: str, limit: int = 20) -> List[dict]:
        try:
            layer = MemoryLayer(layer_name)
        except ValueError:
            return []
        with self._lock:
            return [t.to_dict() for t in sorted(
                self._layers[layer], key=lambda x: -x.effective_strength)[:limit]]

    def _save(self):
        try:
            data = {}
            with self._lock:
                for layer in MemoryLayer:
                    data[layer.value] = [t.to_dict() for t in self._layers[layer][-200:]]
            with open(self._file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug("[TEMPORAL MEMORY] Save error: %s", e)

    def _load(self):
        if not os.path.exists(self._file): return
        try:
            with open(self._file) as f:
                data = json.load(f)
            with self._lock:
                for layer in MemoryLayer:
                    for td in data.get(layer.value, []):
                        try:
                            td_clean = {k: v for k, v in td.items()
                                        if k in MemoryTrace.__dataclass_fields__}
                            td_clean["layer"] = MemoryLayer(td_clean.get("layer", "short"))
                            t = MemoryTrace(**td_clean)
                            self._layers[layer].append(t)
                        except Exception:
                            pass
        except Exception as e:
            logger.debug("[TEMPORAL MEMORY] Load error: %s", e)


_instance: Optional[TemporalMemory] = None
_lock = threading.Lock()

def get_temporal_memory() -> TemporalMemory:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = TemporalMemory()
    return _instance
