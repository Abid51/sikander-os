"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS CONTEXT WINDOW TIME MACHINE                                         ║
║  "Infinite memory inside any LLM context window."                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, json, time, threading, logging, re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ContextSlot:
    slot_type: str    # "full" | "key_decision" | "core_belief" | "personality"
    content: str
    timestamp: str
    importance: float = 0.5
    tokens_approx: int = 0

    def __post_init__(self):
        self.tokens_approx = len(self.content) // 4   # ~4 chars per token


class ContextCompressor:
    """
    Hierarchical compression of conversation history for LLM injection.
    
    Strategy:
    ─────────
    • Recent messages (< 24h):    Full detail (last 10)
    • Last 7 days:                Key decisions & turning points only
    • Last 30 days:               Core beliefs and personality insights
    • Older:                      Nothing (already in Thought Crystallizer)
    
    Target: Always < TARGET_TOKENS tokens for system prompt context.
    """
    DATA_FILE     = "igris_context_compressed.json"
    TARGET_TOKENS = 800    # Max tokens for compressed context block
    MAX_FULL_MSGS = 10     # Keep full text for last N messages

    def __init__(self):
        self._lock = threading.RLock()
        self._all_messages: List[Dict] = []
        self._compressed_cache: Optional[str] = None
        self._cache_dirty: bool = True
        self._message_counter = 0

        base = os.path.dirname(os.path.abspath(__file__))
        self._file = os.path.normpath(os.path.join(base, "..", "..", self.DATA_FILE))
        self._load()
        logger.info("[CONTEXT COMPRESSOR] ⏱️ Context Time Machine online. %d messages loaded.",
                    len(self._all_messages))

    # ─────────────────────────────────────────────────────────────────────
    # INGESTION
    # ─────────────────────────────────────────────────────────────────────

    def add_message(self, role: str, content: str, emotion: str = "",
                    importance: float = None):
        """Add a message to the history buffer."""
        if not content: return
        msg = {
            "role": role,
            "content": content[:500],
            "emotion": emotion,
            "importance": importance or self._estimate_importance(content),
            "timestamp": time.time(),
            "iso": datetime.now().isoformat(),
        }
        with self._lock:
            self._message_counter += 1
            self._all_messages.append(msg)
            if len(self._all_messages) > 10000:
                self._all_messages = self._all_messages[-10000:]
            self._cache_dirty = True

        # Auto-save every 50 messages
        if self._message_counter % 50 == 0:
            threading.Thread(target=self._save, daemon=True).start()

    def _estimate_importance(self, content: str) -> float:
        HIGH_MARKERS = ["decide", "important", "remember", "deadline", "urgent",
                        "promise", "agreed", "final", "confirmed"]
        c = content.lower()
        score = 0.3
        if any(w in c for w in HIGH_MARKERS): score += 0.4
        if len(content) > 100: score += 0.1
        if "?" in content: score += 0.05
        return min(1.0, score)

    # ─────────────────────────────────────────────────────────────────────
    # COMPRESSION & RETRIEVAL
    # ─────────────────────────────────────────────────────────────────────

    def get_compressed_context(self, query: str = "") -> str:
        """Return compressed context block ready for LLM injection."""
        with self._lock:
            if not self._cache_dirty and self._compressed_cache:
                return self._compressed_cache

        parts = []
        now = time.time()
        DAY  = 86400
        WEEK = 7 * DAY

        with self._lock:
            msgs = list(self._all_messages)

        # TIER 1: Recent (last 10 messages) → full detail
        recent = msgs[-self.MAX_FULL_MSGS:]
        if recent:
            lines = []
            for m in recent:
                ts = datetime.fromtimestamp(m["timestamp"]).strftime("%H:%M")
                emo = f"[{m['emotion']}] " if m.get("emotion") else ""
                lines.append(f"  [{ts}] {m['role']}: {emo}{m['content'][:120]}")
            parts.append("[RECENT CONTEXT]:\n" + "\n".join(lines))

        # TIER 2: Last 7 days → key decisions only
        week_msgs = [m for m in msgs[:-self.MAX_FULL_MSGS]
                     if now - m["timestamp"] < WEEK and m.get("importance", 0) >= 0.6]
        if week_msgs:
            key_points = [f"  • {m['content'][:80]}" for m in week_msgs[-10:]]
            parts.append("[KEY DECISIONS (7 days)]:\n" + "\n".join(key_points))

        # TIER 3: Try to pull from crystallizer
        try:
            from app.core.thought_crystallizer import get_crystallizer
            axioms = get_crystallizer().to_prompt_axioms(top_k=3)
            if axioms:
                parts.append(axioms.strip())
        except Exception:
            pass

        # TIER 4: Query-relevant recall
        if query:
            relevant = self._recall_relevant(query, msgs[:-self.MAX_FULL_MSGS], top_k=3)
            if relevant:
                lines = [f"  • {m['content'][:80]}" for m in relevant]
                parts.append("[RELEVANT HISTORY]:\n" + "\n".join(lines))

        compressed = "\n\n".join(parts)

        # Token budget enforcement
        token_approx = len(compressed) // 4
        if token_approx > self.TARGET_TOKENS:
            compressed = compressed[:self.TARGET_TOKENS * 4]
            compressed += "\n[Context truncated — budget limit reached]"

        with self._lock:
            self._compressed_cache = compressed
            self._cache_dirty = False

        return compressed

    def _recall_relevant(self, query: str, msgs: List[Dict], top_k: int) -> List[Dict]:
        q_words = set(re.findall(r'\b\w+\b', query.lower()))
        scored = []
        for m in msgs:
            m_words = set(re.findall(r'\b\w+\b', m["content"].lower()))
            overlap = len(q_words & m_words) / max(len(q_words | m_words), 1)
            if overlap > 0.1:
                scored.append((overlap * m.get("importance", 0.5), m))
        scored.sort(key=lambda x: -x[0])
        return [m for _, m in scored[:top_k]]

    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._all_messages)
            now = time.time()
            return {
                "total_messages": total,
                "message_counter": self._message_counter,
                "recent_24h": sum(1 for m in self._all_messages
                                  if now - m["timestamp"] < 86400),
                "last_week": sum(1 for m in self._all_messages
                                 if now - m["timestamp"] < 7 * 86400),
                "cache_dirty": self._cache_dirty,
                "estimated_tokens": total * 30,
            }

    def get_recent(self, n: int = 20) -> List[dict]:
        with self._lock:
            return list(self._all_messages[-n:])

    def _save(self):
        try:
            with self._lock:
                data = self._all_messages[-5000:]
            with open(self._file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug("[CONTEXT COMPRESSOR] Save error: %s", e)

    def _load(self):
        if not os.path.exists(self._file): return
        try:
            with open(self._file) as f:
                data = json.load(f)
            with self._lock:
                self._all_messages = data if isinstance(data, list) else []
        except Exception as e:
            logger.debug("[CONTEXT COMPRESSOR] Load error: %s", e)


_instance: Optional[ContextCompressor] = None
_lock = threading.Lock()

def get_context_compressor() -> ContextCompressor:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ContextCompressor()
    return _instance
