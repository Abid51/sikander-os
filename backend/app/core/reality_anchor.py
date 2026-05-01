"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS REALITY ANCHOR SYSTEM                                               ║
║  "Every promise you make, I hold forever."                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import re
import json
import time
import threading
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ─── Commitment Patterns ──────────────────────────────────────────────────────

COMMITMENT_PATTERNS = [
    # English
    r"i will\s+(.{5,80})",
    r"i'm going to\s+(.{5,80})",
    r"i'll\s+(.{5,80})",
    r"let me\s+(.{5,80})",
    r"i promise\s+(.{5,80})",
    r"i need to\s+(.{5,80})",
    r"remind me to\s+(.{5,80})",
    r"don't let me forget\s+(.{5,80})",
    r"by (\w+day|\w+) i will\s+(.{5,80})",
    r"deadline[:\s]+(.{5,80})",
    r"goal[:\s]+(.{5,80})",
    r"target[:\s]+(.{5,80})",
    # Roman Urdu
    r"main\s+(\w+\s+){1,6}(karunga|karonga|karun ga)",
    r"kal\s+(.{5,80})",
    r"karna hai\s+(.{5,80})",
    r"bhool mat\s+(.{5,80})",
    r"yaad dilana\s+(.{5,80})",
    r"mujhe\s+(.{5,80})\s+karna hai",
    r"aaj\s+(.{5,80})\s+karna hai",
    r"(\d+)\s*(baje|bajay)\s+(.{5,80})",
]

DEADLINE_PATTERNS = [
    (r"\btomorrow\b",         1),
    (r"\bkal\b",              1),
    (r"\btonight\b",          0),
    (r"\baj raat\b",          0),
    (r"\bnext week\b",        7),
    (r"\bagla hafta\b",       7),
    (r"\bin (\d+) days?\b",  None),  # dynamic
    (r"\bin (\d+) hours?\b", None),
]

PRIORITY_KEYWORDS = {
    "critical": ["urgent", "asap", "jaldi", "emergency", "deadline", "critical"],
    "high":     ["important", "must", "zaroori", "main", "key"],
    "medium":   ["should", "chahiye", "plan", "goal"],
    "low":      ["maybe", "shayad", "sometime", "later", "baad mein"],
}


@dataclass
class Commitment:
    anchor_id: str
    content: str
    source_text: str
    priority: str                  # critical | high | medium | low
    created_at: str
    due_at: Optional[str]          # ISO datetime or None
    completed: bool = False
    reminded: bool = False
    completion_note: Optional[str] = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    def is_overdue(self) -> bool:
        if not self.due_at or self.completed:
            return False
        try:
            return datetime.fromisoformat(self.due_at) < datetime.now()
        except Exception:
            return False


class RealityAnchorSystem:
    """
    Extracts commitments and deadlines from every user message.
    Tracks them persistently and provides smart reminders.
    """

    DATA_FILE   = "igris_anchors.json"
    CHECK_INTERVAL = 300    # seconds between reminder checks

    def __init__(self):
        self._lock = threading.RLock()
        self._anchors: Dict[str, Commitment] = {}
        self._accountability_score: float = 100.0
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._file = os.path.normpath(os.path.join(base_dir, "..", "..", self.DATA_FILE))
        self._load()
        threading.Thread(target=self._reminder_loop, daemon=True).start()
        logger.info("[REALITY ANCHOR] ⚖️  Active. Tracking %d commitments.", len(self._anchors))

    # ──────────────────────────────────────────────────────────────────
    # EXTRACTION
    # ──────────────────────────────────────────────────────────────────

    def extract_and_store(self, text: str) -> List[Commitment]:
        """
        Scan a message for commitments. Store any found.
        Returns list of newly created Commitment objects.
        """
        new_anchors: List[Commitment] = []
        t_lower = text.lower()

        for pattern in COMMITMENT_PATTERNS:
            for match in re.finditer(pattern, t_lower):
                raw = match.group(match.lastindex or 0).strip()
                if len(raw) < 5 or len(raw) > 200:
                    continue

                anchor_id = f"anc_{int(time.time()*1000) % 999999:06d}"
                priority  = self._detect_priority(text)
                due_at    = self._detect_deadline(text)

                commitment = Commitment(
                    anchor_id     = anchor_id,
                    content       = raw.capitalize(),
                    source_text   = text[:100],
                    priority      = priority,
                    created_at    = datetime.now().isoformat(),
                    due_at        = due_at,
                )
                with self._lock:
                    self._anchors[anchor_id] = commitment
                new_anchors.append(commitment)
                logger.info("[REALITY ANCHOR] 📌 New commitment: '%s' [%s]", raw[:50], priority)

        if new_anchors:
            self._save()
        return new_anchors

    def _detect_priority(self, text: str) -> str:
        t = text.lower()
        for priority, keywords in PRIORITY_KEYWORDS.items():
            for kw in keywords:
                if kw in t:
                    return priority
        return "medium"

    def _detect_deadline(self, text: str) -> Optional[str]:
        t = text.lower()
        now = datetime.now()
        for pattern, days in DEADLINE_PATTERNS:
            m = re.search(pattern, t)
            if m:
                if days is None:
                    try:
                        n = int(m.group(1))
                        if "hour" in pattern:
                            return (now + timedelta(hours=n)).isoformat()
                        else:
                            return (now + timedelta(days=n)).isoformat()
                    except Exception:
                        pass
                elif days == 0:
                    return (now + timedelta(hours=6)).isoformat()
                else:
                    return (now + timedelta(days=days)).isoformat()
        return None

    # ──────────────────────────────────────────────────────────────────
    # MANAGEMENT
    # ──────────────────────────────────────────────────────────────────

    def complete(self, anchor_id: str, note: str = "") -> str:
        with self._lock:
            if anchor_id not in self._anchors:
                return f"Anchor {anchor_id} not found."
            self._anchors[anchor_id].completed = True
            self._anchors[anchor_id].completion_note = note
            self._accountability_score = min(100.0, self._accountability_score + 2.0)
            self._save()
        return f"Commitment '{self._anchors[anchor_id].content[:50]}' marked complete. ✅"

    def get_pending(self, priority: Optional[str] = None) -> List[dict]:
        with self._lock:
            result = [a.to_dict() for a in self._anchors.values()
                      if not a.completed
                      and (priority is None or a.priority == priority)]
        result.sort(key=lambda x: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["priority"], 4),
            x.get("due_at") or "9999",
        ))
        return result

    def get_overdue(self) -> List[dict]:
        with self._lock:
            return [a.to_dict() for a in self._anchors.values() if a.is_overdue()]

    def get_accountability_score(self) -> float:
        return round(self._accountability_score, 1)

    # ──────────────────────────────────────────────────────────────────
    # REMINDER LOOP
    # ──────────────────────────────────────────────────────────────────

    def _reminder_loop(self):
        while True:
            time.sleep(self.CHECK_INTERVAL)
            with self._lock:
                for anchor in list(self._anchors.values()):
                    if anchor.completed or anchor.reminded:
                        continue
                    if anchor.is_overdue():
                        logger.warning(
                            "[REALITY ANCHOR] ⚠️  OVERDUE: '%s'", anchor.content[:60]
                        )
                        self._accountability_score = max(0.0, self._accountability_score - 5.0)
                        anchor.reminded = True
            self._save()

    # ──────────────────────────────────────────────────────────────────
    # PERSISTENCE
    # ──────────────────────────────────────────────────────────────────

    def _save(self):
        try:
            data = {a_id: a.to_dict() for a_id, a in self._anchors.items()}
            with open(self._file, "w") as f:
                json.dump({"anchors": data, "score": self._accountability_score}, f, indent=2)
        except Exception as e:
            logger.debug("[REALITY ANCHOR] Save error: %s", e)

    def _load(self):
        if not os.path.exists(self._file):
            return
        try:
            with open(self._file) as f:
                data = json.load(f)
            self._accountability_score = data.get("score", 100.0)
            for a_id, adict in data.get("anchors", {}).items():
                self._anchors[a_id] = Commitment(**adict)
        except Exception as e:
            logger.debug("[REALITY ANCHOR] Load error: %s", e)

    def get_stats(self) -> dict:
        total   = len(self._anchors)
        done    = sum(1 for a in self._anchors.values() if a.completed)
        overdue = sum(1 for a in self._anchors.values() if a.is_overdue())
        return {
            "total":              total,
            "completed":          done,
            "pending":            total - done,
            "overdue":            overdue,
            "accountability_score": self.get_accountability_score(),
            "pending_list":       self.get_pending()[:5],
        }


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[RealityAnchorSystem] = None
_lock = threading.Lock()

def get_reality_anchor() -> RealityAnchorSystem:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RealityAnchorSystem()
    return _instance
