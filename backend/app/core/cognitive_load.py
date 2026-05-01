"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS COGNITIVE LOAD BALANCER                                             ║
║  "I feel when you break. I adapt before you do."                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import re
import time
import threading
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LoadSnapshot:
    score: float          # 0 (fresh) → 10 (overloaded)
    signals: List[str]
    timestamp: str


LOAD_THRESHOLDS = {
    "fresh":      (0.0, 2.0),
    "moderate":   (2.0, 4.5),
    "high":       (4.5, 7.0),
    "overloaded": (7.0, 8.5),
    "burnout":    (8.5, 10.0),
}

RESPONSE_STYLE_MAP = {
    "fresh":      {"length": "normal",       "format": "prose",         "prefix": ""},
    "moderate":   {"length": "normal",       "format": "prose",         "prefix": ""},
    "high":       {"length": "concise",      "format": "bullet_points", "prefix": ""},
    "overloaded": {"length": "very_concise", "format": "bullet_points", "prefix": "Aqa, quick answer: "},
    "burnout":    {"length": "one_liner",    "format": "plain",         "prefix": "Aqa, rest lo. "},
}


class CognitiveLoadBalancer:
    """
    Monitors user cognitive load through message patterns and adapts Igris behavior.

    Signals tracked:
    - Message length (short = rushed / distracted)
    - Message frequency (bursts = stressed)
    - Repeated questions (confusion)
    - Late-night usage
    - Typo density
    - Exclamation / CAPS usage (frustration)
    """

    WINDOW = 10                    # last N messages in sliding window
    COOL_DOWN = 600                # seconds for score to drop naturally by 1 unit

    def __init__(self):
        self._lock = threading.RLock()
        self._message_log: deque = deque(maxlen=self.WINDOW)
        self._load_history: deque = deque(maxlen=200)
        self._current_score: float = 0.0
        self._last_update: float = time.time()
        threading.Thread(target=self._decay_loop, daemon=True).start()
        logger.info("[COGNITIVE LOAD] ⚖️  Balancer online.")

    # ──────────────────────────────────────────────────────────────────
    # ANALYSIS
    # ──────────────────────────────────────────────────────────────────

    def analyze(self, text: str) -> Tuple[float, str, dict]:
        """
        Analyze a message and update the load score.
        Returns (score, state_label, style_config).
        """
        now = time.time()
        with self._lock:
            self._message_log.append({"text": text, "ts": now})
            score = self._compute_score(text, now)
            self._current_score = min(10.0, max(0.0,
                self._current_score * 0.6 + score * 0.4))   # smooth update
            self._last_update = now

            state = self._get_state(self._current_score)
            snap = LoadSnapshot(score=self._current_score, signals=self._extract_signals(text),
                                timestamp=datetime.now().isoformat())
            self._load_history.append(snap)

        style = RESPONSE_STYLE_MAP[state]
        logger.debug("[COGNITIVE LOAD] score=%.1f  state=%s", self._current_score, state)
        return self._current_score, state, style

    def _compute_score(self, text: str, now: float) -> float:
        score = 0.0
        words = text.split()
        word_count = len(words)

        # Very short message = rushed
        if word_count <= 2:
            score += 2.0
        elif word_count <= 5:
            score += 1.0

        # Message burst rate (many messages in short time)
        recent = [m for m in self._message_log if now - m["ts"] < 120]
        if len(recent) >= 5:
            score += 2.5
        elif len(recent) >= 3:
            score += 1.0

        # Late night (11 PM – 4 AM)
        hour = datetime.now().hour
        if hour >= 23 or hour <= 4:
            score += 1.5

        # CAPS usage
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        if caps_ratio > 0.4:
            score += 1.5

        # Exclamation marks
        if text.count("!") >= 2:
            score += 1.0

        # Simple typo hint: very short words mixed with long text
        typo_hint = sum(1 for w in words if len(w) == 1 and w.isalpha()) / max(word_count, 1)
        score += typo_hint * 2.0

        # Repeated last message (confusion)
        if len(self._message_log) >= 2:
            prev = list(self._message_log)[-2]["text"].lower()
            if text.lower()[:30] == prev[:30]:
                score += 2.0

        return min(score, 10.0)

    def _extract_signals(self, text: str) -> List[str]:
        signals = []
        if len(text.split()) <= 3:
            signals.append("short_message")
        if datetime.now().hour >= 23 or datetime.now().hour <= 4:
            signals.append("late_night")
        if text.count("!") >= 2:
            signals.append("exclamation_burst")
        caps = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        if caps > 0.4:
            signals.append("caps_usage")
        return signals

    @staticmethod
    def _get_state(score: float) -> str:
        for state, (lo, hi) in LOAD_THRESHOLDS.items():
            if lo <= score < hi:
                return state
        return "burnout"

    # ──────────────────────────────────────────────────────────────────
    # ADAPTATION
    # ──────────────────────────────────────────────────────────────────

    def get_response_style(self) -> dict:
        with self._lock:
            state = self._get_state(self._current_score)
        return RESPONSE_STYLE_MAP[state]

    def build_prompt_context(self) -> str:
        """Returns a context string to inject into the system prompt."""
        with self._lock:
            score = self._current_score
        state = self._get_state(score)
        style = RESPONSE_STYLE_MAP[state]
        if state in ("fresh", "moderate"):
            return ""   # No modification needed
        return (
            f"\n[COGNITIVE LOAD: {state.upper()} score={score:.1f}/10] "
            f"User appears {state}. "
            f"Response must be {style['length']}. "
            f"Format: {style['format']}. "
            f"{style['prefix']}"
        )

    # ──────────────────────────────────────────────────────────────────
    # DECAY LOOP
    # ──────────────────────────────────────────────────────────────────

    def _decay_loop(self):
        """Naturally reduce load score over time (rest = recovery)."""
        while True:
            time.sleep(60)
            with self._lock:
                elapsed_min = (time.time() - self._last_update) / 60
                decay = elapsed_min * (10.0 / (self.COOL_DOWN / 60))
                self._current_score = max(0.0, self._current_score - decay)

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────

    @property
    def current_score(self) -> float:
        return round(self._current_score, 2)

    @property
    def current_state(self) -> str:
        return self._get_state(self._current_score)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "current_score":  self.current_score,
                "current_state":  self.current_state,
                "response_style": self.get_response_style(),
                "history_size":   len(self._load_history),
                "recent_signals": [
                    {"score": s.score, "signals": s.signals, "ts": s.timestamp}
                    for s in list(self._load_history)[-5:]
                ],
            }


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[CognitiveLoadBalancer] = None
_lock = threading.Lock()

def get_cognitive_load_balancer() -> CognitiveLoadBalancer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = CognitiveLoadBalancer()
    return _instance
