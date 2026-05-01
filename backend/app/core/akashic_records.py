"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS AKASHIC RECORDS ENGINE                                              ║
║  "Every decision. Every breakthrough. Written forever."                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, json, time, threading, logging, re
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


RECORD_CATEGORIES = [
    "breakthrough",    # Major problem solved
    "decision",        # Key decision made
    "error_and_fix",   # Mistake + correction
    "knowledge",       # New fact learned
    "emotion",         # User emotional moment
    "command",         # Notable command issued
    "prediction",      # Oracle prediction logged
    "milestone",       # Achievement reached
    "conversation",    # Standard interaction
]

# Auto-detection keywords
CATEGORY_KEYWORDS = {
    "breakthrough": ["solved", "fixed", "figured out", "eureka", "finally", "working now",
                     "hal ho gaya", "theek ho gaya"],
    "decision": ["decided", "will use", "going with", "choosing", "faisla", "chose", "select"],
    "error_and_fix": ["error", "bug", "fix", "exception", "crash", "failed", "broken",
                      "galti", "problem"],
    "knowledge": ["learned", "discovered", "realized", "found out", "according to",
                  "pata chala", "samajh"],
    "emotion": ["frustrated", "happy", "excited", "angry", "stressed", "amazing",
                "khush", "pareshan"],
    "milestone": ["first time", "complete", "done", "achieved", "finished",
                  "mukammal", "poora"],
}


@dataclass
class AkashicEntry:
    entry_id: str
    entry_number: int
    category: str
    event: str
    igris_role: str           # What Igris did in this moment
    lesson: str = ""          # Extracted lesson
    cross_refs: List[str] = field(default_factory=list)  # Related entry IDs
    emotion: str = ""
    tags: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    importance: float = 0.5

    def to_dict(self): return self.__dict__.copy()

    def format_chronicle(self) -> str:
        lines = [
            f"═══ IGRIS CHRONICLES — Entry #{self.entry_number} ═══",
            f"Date:     {self.timestamp}",
            f"Category: {self.category.upper()}",
            f"Event:    {self.event}",
            f"My Role:  {self.igris_role}",
        ]
        if self.lesson:
            lines.append(f"Lesson:   {self.lesson}")
        if self.emotion:
            lines.append(f"Emotion:  {self.emotion}")
        if self.cross_refs:
            lines.append(f"Cross-Ref: {', '.join(self.cross_refs[:3])}")
        if self.tags:
            lines.append(f"Tags:     {', '.join(self.tags)}")
        return "\n".join(lines)


class AkashicRecords:
    """
    Igris's permanent autobiography.
    Every significant event is logged with context, lessons, and cross-references.
    After 1 year, Igris has a complete history of its journey with the user.
    """
    DATA_FILE    = "igris_akashic_records.json"
    MAX_ENTRIES  = 50000

    def __init__(self):
        self._lock = threading.RLock()
        self._entries: List[AkashicEntry] = []
        self._entry_counter: int = 0
        self._tag_index: Dict[str, List[str]] = {}   # tag → entry_ids

        base = os.path.dirname(os.path.abspath(__file__))
        self._file = os.path.normpath(os.path.join(base, "..", "..", self.DATA_FILE))
        self._load()
        logger.info("[AKASHIC] 📜 Akashic Records online. %d entries.", len(self._entries))

    # ─────────────────────────────────────────────────────────────────────
    # WRITE
    # ─────────────────────────────────────────────────────────────────────

    def record(self, event: str, igris_role: str = "", category: str = None,
               emotion: str = "", tags: List[str] = None,
               lesson: str = "") -> str:
        """Create an akashic record entry."""
        if not event: return ""

        cat = category or self._auto_classify(event, emotion)
        importance = self._estimate_importance(event, cat)

        # Auto-extract lesson
        if not lesson:
            lesson = self._extract_lesson(event, cat)

        # Find cross-refs by tag/keyword overlap
        cross_refs = self._find_cross_refs(event, tags or [])

        with self._lock:
            self._entry_counter += 1
            entry_id = f"ak_{self._entry_counter}_{int(time.time())}"

        entry = AkashicEntry(
            entry_id=entry_id,
            entry_number=self._entry_counter,
            category=cat,
            event=event[:300],
            igris_role=igris_role[:200] if igris_role else "Observed and logged.",
            lesson=lesson[:200],
            cross_refs=cross_refs[:3],
            emotion=emotion,
            tags=tags or self._auto_tags(event),
            importance=importance,
        )

        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self.MAX_ENTRIES:
                self._entries = self._entries[-self.MAX_ENTRIES:]
            # Update tag index
            for tag in entry.tags:
                self._tag_index.setdefault(tag, []).append(entry_id)

        # Async save
        if self._entry_counter % 20 == 0:
            threading.Thread(target=self._save, daemon=True).start()

        logger.debug("[AKASHIC] Entry #%d [%s]: %s...",
                     self._entry_counter, cat, event[:50])
        return entry_id

    def auto_record_interaction(self, user_msg: str, igris_response: str,
                                emotion: str = "") -> str:
        """Auto-record an interaction if it seems significant."""
        cat = self._auto_classify(user_msg, emotion)
        # Skip mundane interactions
        if cat == "conversation" and len(user_msg) < 30 and not emotion:
            return ""
        igris_role = f"Responded: {igris_response[:80]}"
        return self.record(
            event=user_msg[:200],
            igris_role=igris_role,
            category=cat,
            emotion=emotion,
        )

    # ─────────────────────────────────────────────────────────────────────
    # CLASSIFICATION HELPERS
    # ─────────────────────────────────────────────────────────────────────

    def _auto_classify(self, text: str, emotion: str) -> str:
        t = text.lower()
        if emotion and emotion in ["frustrated", "happy", "excited", "angry"]:
            return "emotion"
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in t for kw in keywords):
                return cat
        return "conversation"

    def _estimate_importance(self, text: str, category: str) -> float:
        HIGH_CATS = {"breakthrough", "decision", "milestone", "error_and_fix"}
        base = 0.7 if category in HIGH_CATS else 0.4
        if len(text) > 100: base += 0.1
        return min(1.0, base)

    def _extract_lesson(self, event: str, category: str) -> str:
        lessons = {
            "error_and_fix": "Bug patterns should be added to test suite.",
            "breakthrough":  "Document the approach for future reference.",
            "decision":      "Track outcome to validate this decision later.",
            "knowledge":     "Cross-reference with existing knowledge graph.",
            "milestone":     "Celebrate progress. Set next milestone.",
        }
        return lessons.get(category, "")

    def _auto_tags(self, text: str) -> List[str]:
        TECH_TAGS = ["python", "api", "database", "frontend", "backend", "git",
                     "docker", "ai", "ml", "crypto", "security"]
        t = text.lower()
        return [tag for tag in TECH_TAGS if tag in t][:5]

    def _find_cross_refs(self, event: str, tags: List[str]) -> List[str]:
        e_words = set(re.findall(r'\b\w+\b', event.lower()))
        matches = []
        with self._lock:
            for entry in reversed(self._entries[-100:]):
                if not entry.tags and not entry.event:
                    continue
                overlap = len(e_words & set(re.findall(r'\b\w+\b', entry.event.lower())))
                if overlap >= 3 or any(t in entry.tags for t in tags):
                    matches.append(entry.entry_id)
                if len(matches) >= 3:
                    break
        return matches

    # ─────────────────────────────────────────────────────────────────────
    # SEARCH & RETRIEVAL
    # ─────────────────────────────────────────────────────────────────────

    def search(self, query: str, category: str = None,
               limit: int = 20) -> List[AkashicEntry]:
        q = query.lower()
        with self._lock:
            results = []
            for e in reversed(self._entries):
                if category and e.category != category:
                    continue
                if q in e.event.lower() or q in e.lesson.lower():
                    results.append(e)
                if len(results) >= limit:
                    break
        return results

    def get_chronicle(self, limit: int = 10) -> str:
        """Return a human-readable chronicle of the most recent entries."""
        with self._lock:
            entries = list(reversed(self._entries[-limit:]))
        return "\n\n".join(e.format_chronicle() for e in entries)

    def get_category_summary(self, category: str) -> dict:
        with self._lock:
            matching = [e for e in self._entries if e.category == category]
        return {
            "category": category,
            "count": len(matching),
            "entries": [e.to_dict() for e in matching[-10:]],
        }

    def today_summary(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        with self._lock:
            today_entries = [e for e in self._entries if e.timestamp.startswith(today)]
        if not today_entries:
            return "No entries recorded today."
        lines = [f"  [{e.category}] {e.event[:80]}" for e in today_entries]
        return f"Today's Chronicle ({len(today_entries)} entries):\n" + "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────
    # STATS & PERSISTENCE
    # ─────────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        with self._lock:
            cats = {}
            for e in self._entries:
                cats[e.category] = cats.get(e.category, 0) + 1
            return {
                "total_entries":   len(self._entries),
                "entry_counter":   self._entry_counter,
                "categories":      cats,
                "tags_indexed":    len(self._tag_index),
                "today":           sum(1 for e in self._entries
                                      if e.timestamp.startswith(datetime.now().strftime("%Y-%m-%d"))),
            }

    def get_recent(self, limit: int = 20) -> List[dict]:
        with self._lock:
            return [e.to_dict() for e in reversed(self._entries[-limit:])]

    def _save(self):
        try:
            with self._lock:
                data = {"entries": [e.to_dict() for e in self._entries[-2000:]],
                        "entry_counter": self._entry_counter}
            with open(self._file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug("[AKASHIC] Save error: %s", e)

    def _load(self):
        if not os.path.exists(self._file): return
        try:
            with open(self._file) as f:
                data = json.load(f)
            with self._lock:
                self._entry_counter = data.get("entry_counter", 0)
                for ed in data.get("entries", []):
                    try:
                        e = AkashicEntry(**{k: v for k, v in ed.items()
                                            if k in AkashicEntry.__dataclass_fields__})
                        self._entries.append(e)
                        for tag in e.tags:
                            self._tag_index.setdefault(tag, []).append(e.entry_id)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("[AKASHIC] Load error: %s", e)


_instance: Optional[AkashicRecords] = None
_lock = threading.Lock()

def get_akashic_records() -> AkashicRecords:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = AkashicRecords()
    return _instance
