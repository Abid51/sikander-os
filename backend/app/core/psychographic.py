"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS PSYCHOGRAPHIC INTELLIGENCE ENGINE                                   ║
║  "Know the user deeper than they know themselves."                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, re, json, time, threading, logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class PsychographicProfile:
    # Big Five
    openness:          float = 0.5   # curiosity, creativity
    conscientiousness: float = 0.5   # organized, dependable
    extraversion:      float = 0.3   # social energy
    agreeableness:     float = 0.5   # cooperative
    neuroticism:       float = 0.4   # emotional stability (0=stable)

    # Cognitive style
    analytical:    float = 0.5
    intuitive:     float = 0.5
    detail_focus:  float = 0.5
    big_picture:   float = 0.5

    # Communication preferences
    prefers_direct:   bool = True
    prefers_examples: bool = True
    prefers_brief:    bool = False
    prefers_urdu:     bool = False

    # Usage patterns
    peak_hour:       int = 23       # Most active hour (24h)
    avg_msg_length:  float = 50.0
    avg_response_time_pref: float = 2.0   # seconds
    total_interactions: int = 0

    # Inferred traits
    is_night_owl:    bool = True
    is_developer:    bool = False
    is_analytical:   bool = False
    stress_level:    float = 0.3   # 0=calm, 1=stressed
    confidence:      float = 0.3   # profile confidence

    def mbti(self) -> str:
        E_or_I = "E" if self.extraversion > 0.5 else "I"
        S_or_N = "N" if self.openness > 0.5 else "S"
        T_or_F = "T" if self.analytical > self.agreeableness else "F"
        J_or_P = "J" if self.conscientiousness > 0.5 else "P"
        return f"{E_or_I}{S_or_N}{T_or_F}{J_or_P}"

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["mbti"] = self.mbti()
        d["confidence_pct"] = f"{self.confidence:.0%}"
        return d


# Signal weights for trait extraction
TRAIT_SIGNALS = {
    "openness": {
        "positive": ["curious", "interesting", "idea", "creative", "design", "art",
                     "philosophy", "explore", "learn", "try", "experiment"],
        "negative": ["boring", "complicated", "not interested", "skip"],
    },
    "conscientiousness": {
        "positive": ["plan", "organize", "deadline", "schedule", "precise", "correct",
                     "accurate", "test", "verify", "double check"],
        "negative": ["whatever", "lazy", "skip", "later", "doesn't matter"],
    },
    "analytical": {
        "positive": ["because", "therefore", "analyze", "data", "why", "how", "reason",
                     "logic", "explain", "proof", "code", "debug", "algorithm"],
        "negative": ["feel", "gut", "instinct", "seems like"],
    },
    "is_developer": {
        "positive": ["code", "function", "api", "debug", "python", "javascript", "git",
                     "backend", "frontend", "deploy", "server", "database", "framework"],
        "negative": [],
    },
    "stress": {
        "positive": ["urgent", "asap", "help", "broken", "error", "crash", "deadline",
                     "why is", "not working", "fix this", "problem"],
        "negative": ["great", "perfect", "awesome", "thanks", "cool"],
    },
    "prefers_brief": {
        "positive": ["short", "brief", "tldr", "quick", "summary", "just tell",
                     "don't explain", "fast"],
        "negative": ["explain", "detail", "elaborate", "how", "step by step"],
    },
}

class PsychographicEngine:
    """
    Builds a deep psychological profile of the user from conversation patterns.
    Profile evolves with every interaction.
    Used to adapt Igris communication style automatically.
    """
    DATA_FILE = "igris_psychographic.json"
    SAVE_INTERVAL = 60

    def __init__(self):
        self._lock = threading.RLock()
        self._profile = PsychographicProfile()
        self._hour_counter = Counter()
        self._msg_lengths: List[int] = []
        self._interaction_count = 0
        self._urdu_count = 0
        self._english_count = 0

        base = os.path.dirname(os.path.abspath(__file__))
        self._file = os.path.normpath(os.path.join(base, "..", "..", self.DATA_FILE))
        self._load()
        threading.Thread(target=self._save_loop, daemon=True).start()
        logger.info("[PSYCHOGRAPHIC] 🧠 Psychographic Intelligence Engine online.")

    # ─────────────────────────────────────────────────────────────────────
    # OBSERVE
    # ─────────────────────────────────────────────────────────────────────

    def observe(self, message: str, response_latency_ms: float = None,
                emotion: str = None):
        """Process a user message and update the profile."""
        if not message:
            return

        with self._lock:
            self._interaction_count += 1
            self._profile.total_interactions = self._interaction_count

            # Hour tracking
            hour = datetime.now().hour
            self._hour_counter[hour] += 1
            self._profile.peak_hour = self._hour_counter.most_common(1)[0][0]
            self._profile.is_night_owl = self._profile.peak_hour >= 21 or self._profile.peak_hour <= 4

            # Message length
            self._msg_lengths.append(len(message))
            if len(self._msg_lengths) > 100:
                self._msg_lengths = self._msg_lengths[-100:]
            self._profile.avg_msg_length = sum(self._msg_lengths) / len(self._msg_lengths)

            # Language detection
            urdu_chars = sum(1 for c in message if '\u0600' <= c <= '\u06ff')
            if urdu_chars > 5:
                self._urdu_count += 1
            else:
                self._english_count += 1
            total_lang = self._urdu_count + self._english_count
            self._profile.prefers_urdu = self._urdu_count / max(total_lang, 1) > 0.6

            # Trait signals
            m_lower = message.lower()
            n = self._interaction_count
            alpha = 2 / (n + 1)   # EMA factor

            for trait, signals in TRAIT_SIGNALS.items():
                pos = sum(1 for w in signals["positive"] if w in m_lower)
                neg = sum(1 for w in signals["negative"] if w in m_lower)
                signal = 0.0
                if pos > 0: signal += pos * 0.1
                if neg > 0: signal -= neg * 0.1

                if signal != 0:
                    current = getattr(self._profile, trait, None)
                    if isinstance(current, float):
                        new_val = current * (1 - alpha) + (0.5 + signal) * alpha
                        setattr(self._profile, trait, max(0.0, min(1.0, new_val)))
                    elif isinstance(current, bool) and signal > 0:
                        setattr(self._profile, trait, True)

            # Direct preference signals
            if any(w in m_lower for w in ["short", "brief", "tldr", "quick answer"]):
                self._profile.prefers_brief = True
            if any(w in m_lower for w in ["explain", "detail", "step by step", "elaborate"]):
                self._profile.prefers_brief = False

            # Update confidence
            self._profile.confidence = min(1.0, self._interaction_count / 100)

            # Stress from emotion
            if emotion:
                if emotion in ["angry", "frustrated", "anxious"]:
                    self._profile.stress_level = min(1.0, self._profile.stress_level + 0.1)
                elif emotion in ["happy", "calm", "excited"]:
                    self._profile.stress_level = max(0.0, self._profile.stress_level - 0.05)

    # ─────────────────────────────────────────────────────────────────────
    # ADAPTATION
    # ─────────────────────────────────────────────────────────────────────

    def get_communication_style(self) -> dict:
        """Returns recommended communication style based on profile."""
        p = self._profile
        return {
            "tone":       "direct" if p.prefers_direct else "diplomatic",
            "length":     "brief" if p.prefers_brief else "detailed",
            "language":   "urdu_mix" if p.prefers_urdu else "english",
            "examples":   p.prefers_examples,
            "technical":  p.is_developer,
            "urgency":    "high" if p.stress_level > 0.7 else "normal",
        }

    def to_prompt_context(self) -> str:
        if self._profile.confidence < 0.1:
            return ""
        p = self._profile
        style = self.get_communication_style()
        return (f"\n[PSYCHOGRAPHIC PROFILE (confidence={p.confidence:.0%})]:\n"
                f"  MBTI: {p.mbti()} | Peak Hours: {p.peak_hour}:00 | "
                f"Night Owl: {p.is_night_owl} | Developer: {p.is_developer}\n"
                f"  Style: {style['tone']}, {style['length']} answers | "
                f"Stress Level: {p.stress_level:.0%}\n")

    # ─────────────────────────────────────────────────────────────────────
    # PERSISTENCE & API
    # ─────────────────────────────────────────────────────────────────────

    def get_profile(self) -> dict:
        with self._lock:
            return self._profile.to_dict()

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_interactions": self._interaction_count,
                "profile_confidence": f"{self._profile.confidence:.0%}",
                "mbti": self._profile.mbti(),
                "peak_hour": self._profile.peak_hour,
                "prefers_urdu": self._profile.prefers_urdu,
                "is_developer": self._profile.is_developer,
                "stress_level": round(self._profile.stress_level, 2),
                "prefers_brief": self._profile.prefers_brief,
            }

    def _save_loop(self):
        while True:
            time.sleep(self.SAVE_INTERVAL)
            try:
                with self._lock:
                    data = {"profile": self._profile.to_dict(),
                            "hour_counter": dict(self._hour_counter),
                            "interaction_count": self._interaction_count,
                            "urdu_count": self._urdu_count,
                            "english_count": self._english_count}
                with open(self._file, "w") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                logger.debug("[PSYCHOGRAPHIC] Save error: %s", e)

    def _load(self):
        if not os.path.exists(self._file): return
        try:
            with open(self._file) as f:
                data = json.load(f)
            with self._lock:
                self._hour_counter.update(
                    {int(k): v for k, v in data.get("hour_counter", {}).items()})
                self._interaction_count = data.get("interaction_count", 0)
                self._urdu_count  = data.get("urdu_count", 0)
                self._english_count = data.get("english_count", 0)
                prof_data = data.get("profile", {})
                for k, v in prof_data.items():
                    if k in self._profile.__dataclass_fields__ and k != "mbti" and k != "confidence_pct":
                        try:
                            setattr(self._profile, k, v)
                        except Exception:
                            pass
        except Exception as e:
            logger.debug("[PSYCHOGRAPHIC] Load error: %s", e)


_instance: Optional[PsychographicEngine] = None
_lock = threading.Lock()

def get_psychographic() -> PsychographicEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = PsychographicEngine()
    return _instance
