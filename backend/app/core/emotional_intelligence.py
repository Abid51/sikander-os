"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         IGRIS EMOTIONAL INTELLIGENCE ENGINE                                ║
║         "I feel what you feel. I know before you speak."                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import re
import time
import json
import math
import threading
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import deque, defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#                          EMOTION TAXONOMY
# ═══════════════════════════════════════════════════════════════════════════════

EMOTION_KEYWORDS = {
    "frustrated": [
        "nahi", "nahi chal raha", "kaam nahi", "problem", "error", "fix", "broken",
        "again", "still", "ugh", "damn", "shit", "wtf", "why", "help", "stuck",
        "kyu", "kyun", "naraz", "gussa", "nahi ho raha", "fail"
    ],
    "happy": [
        "amazing", "great", "perfect", "love", "awesome", "excellent", "wow",
        "maza", "zabardast", "kya baat", "shukriya", "thanks", "worked", "done",
        "finally", "yes", "yay", "nice", "good job", "mast", "badhiya", "khushi"
    ],
    "curious": [
        "kya", "how", "why", "what", "explain", "tell me", "batao", "samjhao",
        "kyun", "kaise", "idea", "concept", "learn", "understand", "sikhao"
    ],
    "focused": [
        "build", "code", "implement", "create", "make", "develop", "write",
        "banao", "likho", "karo", "start", "begin", "execute", "run", "deploy"
    ],
    "tired": [
        "kal", "baad mein", "later", "sleep", "rest", "thak", "tired", "break",
        "pause", "stop", "enough", "bas", "kal karte", "tomorrow", "abhi nahi"
    ],
    "urgent": [
        "jaldi", "fast", "quickly", "asap", "urgent", "now", "abhi", "immediately",
        "emergency", "critical", "deadline", "hurry", "rush"
    ],
    "proud": [
        "complete", "finish", "done", "achieved", "success", "worked", "ho gaya",
        "ban gaya", "mil gaya", "kar diya", "amazing result", "perfect output"
    ],
}

RESPONSE_STYLE = {
    "frustrated": {
        "tone": "calm, empathetic, solution-focused",
        "prefix": "Aqa, main samajhta hun. Chalte hain step by step.",
        "emoji_style": "minimal",
        "response_length": "concise",
    },
    "happy": {
        "tone": "energetic, celebratory, enthusiastic",
        "prefix": "Aqa, yeh sun ke khushi hui!",
        "emoji_style": "rich",
        "response_length": "detailed",
    },
    "curious": {
        "tone": "educational, thoughtful, detailed",
        "prefix": "Bohat acha sawaal, Aqa.",
        "emoji_style": "moderate",
        "response_length": "detailed",
    },
    "focused": {
        "tone": "direct, efficient, code-first",
        "prefix": "Hukum. Executing immediately.",
        "emoji_style": "minimal",
        "response_length": "concise",
    },
    "tired": {
        "tone": "gentle, supportive, brief",
        "prefix": "Aqa, rest karo. Main sab sambhal lunga.",
        "emoji_style": "minimal",
        "response_length": "very_concise",
    },
    "urgent": {
        "tone": "fast, direct, action-oriented",
        "prefix": "EXECUTING NOW, Aqa!",
        "emoji_style": "none",
        "response_length": "bullet_points",
    },
    "proud": {
        "tone": "celebratory, motivating",
        "prefix": "Shabash, Aqa! Ye achievement qabil-e-fakhr hai!",
        "emoji_style": "rich",
        "response_length": "detailed",
    },
    "neutral": {
        "tone": "balanced, professional",
        "prefix": "Hukum Mere Aqa.",
        "emoji_style": "moderate",
        "response_length": "standard",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#                          EMOTIONAL STATE MACHINE
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class EmotionState:
    primary: str = "neutral"
    secondary: Optional[str] = None
    confidence: float = 0.5
    valence: float = 0.0       # -1.0 (negative) to +1.0 (positive)
    arousal: float = 0.5       # 0.0 (calm) to 1.0 (excited)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    raw_scores: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "primary": self.primary,
            "secondary": self.secondary,
            "confidence": round(self.confidence, 3),
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "timestamp": self.timestamp,
        }


class EmotionalIntelligenceEngine:
    """
    Igris Emotional Intelligence Engine.

    Features:
    ─────────
    • Multi-signal emotion detection (text, typing speed, message length, frequency)
    • Emotion state machine with momentum (emotions don't flip instantly)
    • Long-term mood tracking (session + historical)
    • Dynamic response style adaptation
    • Frustration escalation detection (alert before user rage-quits)
    • Empathy injection into AI prompts
    """

    HISTORY_SIZE = 200
    MOMENTUM_DECAY = 0.7        # How much previous emotion influences current
    FRUSTRATION_THRESHOLD = 0.6  # Alert if frustration exceeds this

    def __init__(self):
        self._lock = threading.RLock()
        self._state = EmotionState()
        self._history: deque = deque(maxlen=self.HISTORY_SIZE)
        self._message_timestamps: deque = deque(maxlen=50)
        self._frustration_alerts: List[dict] = []
        self._session_mood_track: List[float] = []  # valence over time
        self._emotion_counts = defaultdict(int)

        # Negative word amplifiers
        self._negation_words = {"nahi", "not", "no", "never", "na", "mat"}
        self._intensifiers = {"bohat", "bahut", "very", "extremely", "so", "too", "zyada"}

        threading.Thread(target=self._mood_analysis_loop, daemon=True).start()
        logger.info("[EMOTIONAL AI] 🧠 Emotional Intelligence Engine online.")

    # ──────────────────────────────────────────────────────────────────────────
    # CORE: EMOTION DETECTION
    # ──────────────────────────────────────────────────────────────────────────

    def analyze(self, text: str, typing_speed_wpm: Optional[float] = None) -> EmotionState:
        """
        Analyze text and return an EmotionState.
        Considers text semantics + behavioral signals (typing speed, message rate).
        """
        now = time.time()
        self._message_timestamps.append(now)

        scores = self._score_text(text)
        behavioral_scores = self._score_behavioral(typing_speed_wpm)

        # Combine scores
        combined: Dict[str, float] = {}
        for emotion in EMOTION_KEYWORDS:
            combined[emotion] = scores.get(emotion, 0.0) * 0.75 + behavioral_scores.get(emotion, 0.0) * 0.25

        # Apply momentum from previous state
        prev_emotion = self._state.primary
        if prev_emotion in combined:
            combined[prev_emotion] = combined[prev_emotion] * (1 - self.MOMENTUM_DECAY) + \
                                     self._state.confidence * self.MOMENTUM_DECAY

        # Determine primary + secondary
        sorted_emotions = sorted(combined.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_emotions[0][0] if sorted_emotions and sorted_emotions[0][1] > 0.05 else "neutral"
        confidence = sorted_emotions[0][1] if sorted_emotions else 0.5
        secondary = sorted_emotions[1][0] if len(sorted_emotions) > 1 and sorted_emotions[1][1] > 0.1 else None

        # Compute valence and arousal
        valence = self._compute_valence(primary, combined)
        arousal = self._compute_arousal(primary, text)

        new_state = EmotionState(
            primary=primary,
            secondary=secondary,
            confidence=min(confidence, 1.0),
            valence=valence,
            arousal=arousal,
            raw_scores=combined,
        )

        with self._lock:
            self._state = new_state
            self._history.append(new_state)
            self._emotion_counts[primary] += 1
            self._session_mood_track.append(valence)

        # Check frustration escalation
        self._check_frustration_escalation(new_state, text)

        logger.debug(f"[EMOTIONAL AI] {primary} (conf={confidence:.2f}, val={valence:.2f})")
        return new_state

    def analyze_emotion(self, text: str) -> dict:
        """Alias for :meth:`analyze` returning a plain dict (incl. ``emotion`` for legacy callers)."""
        st = self.analyze(text)
        d = st.to_dict()
        d["emotion"] = d.get("primary", "neutral")
        d["dominant_emotion"] = d["emotion"]
        d["raw_scores"] = st.raw_scores
        return d

    def _score_text(self, text: str) -> Dict[str, float]:
        """Score text against each emotion's keyword list."""
        words = re.findall(r'\b\w+\b', text.lower())
        word_set = set(words)
        scores: Dict[str, float] = {}

        for emotion, keywords in EMOTION_KEYWORDS.items():
            hits = 0
            for kw in keywords:
                kw_words = kw.lower().split()
                if len(kw_words) == 1:
                    if kw in word_set:
                        hits += 1
                        # Check for intensifiers nearby
                        for i, w in enumerate(words):
                            if w == kw and i > 0 and words[i-1] in self._intensifiers:
                                hits += 0.5
                else:
                    if kw in text.lower():
                        hits += 1.5  # Multi-word phrases are stronger signals

            # Normalize by keyword count
            scores[emotion] = hits / max(len(keywords), 1)

            # Handle negation: "nahi maza aaya" → not happy
            if emotion == "happy":
                for neg in self._negation_words:
                    if neg in word_set:
                        scores[emotion] *= 0.3

        return scores

    def _score_behavioral(self, typing_speed_wpm: Optional[float]) -> Dict[str, float]:
        """Infer emotion from behavioral signals."""
        behavioral: Dict[str, float] = {}

        # Message frequency (messages per minute)
        if len(self._message_timestamps) >= 2:
            recent = list(self._message_timestamps)[-10:]
            if len(recent) >= 2:
                duration = recent[-1] - recent[0]
                rate = len(recent) / max(duration / 60, 0.1)
                if rate > 8:   # Very fast messages → frustrated or urgent
                    behavioral["frustrated"] = 0.4
                    behavioral["urgent"] = 0.3
                elif rate < 1:  # Slow messages → tired or thoughtful
                    behavioral["tired"] = 0.2
                    behavioral["curious"] = 0.1

        # Typing speed (if provided by frontend)
        if typing_speed_wpm:
            if typing_speed_wpm > 80:
                behavioral["urgent"] = behavioral.get("urgent", 0) + 0.3
                behavioral["focused"] = behavioral.get("focused", 0) + 0.2
            elif typing_speed_wpm < 20:
                behavioral["tired"] = behavioral.get("tired", 0) + 0.3

        return behavioral

    def _compute_valence(self, primary: str, scores: Dict[str, float]) -> float:
        valence_map = {
            "happy": 0.8, "proud": 0.7, "curious": 0.3, "focused": 0.2,
            "neutral": 0.0, "tired": -0.2, "frustrated": -0.7, "urgent": -0.1,
        }
        return valence_map.get(primary, 0.0)

    def _compute_arousal(self, primary: str, text: str) -> float:
        arousal_map = {
            "urgent": 0.95, "frustrated": 0.8, "happy": 0.7, "focused": 0.6,
            "curious": 0.5, "proud": 0.5, "neutral": 0.4, "tired": 0.1,
        }
        base = arousal_map.get(primary, 0.4)
        # Uppercase letters boost arousal
        uppercase_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        return min(base + uppercase_ratio * 0.5, 1.0)

    # ──────────────────────────────────────────────────────────────────────────
    # FRUSTRATION ESCALATION DETECTOR
    # ──────────────────────────────────────────────────────────────────────────

    def _check_frustration_escalation(self, state: EmotionState, text: str):
        if state.primary == "frustrated" and state.confidence > self.FRUSTRATION_THRESHOLD:
            # Check if frustration is increasing over recent messages
            recent_emotions = [h.primary for h in list(self._history)[-5:]]
            frustration_streak = sum(1 for e in recent_emotions if e == "frustrated")
            if frustration_streak >= 3:
                alert = {
                    "alert": "FRUSTRATION_ESCALATION",
                    "streak": frustration_streak,
                    "confidence": state.confidence,
                    "timestamp": datetime.now().isoformat(),
                }
                self._frustration_alerts.append(alert)
                logger.warning(f"[EMOTIONAL AI] ⚠️ Frustration escalating! Streak: {frustration_streak}")

    # ──────────────────────────────────────────────────────────────────────────
    # RESPONSE ADAPTATION
    # ──────────────────────────────────────────────────────────────────────────

    def get_response_style(self, emotion: str = None) -> dict:
        """Get the recommended response style for current emotion."""
        em = emotion or self._state.primary
        return RESPONSE_STYLE.get(em, RESPONSE_STYLE["neutral"])

    def adapt_system_prompt(self, base_prompt: str, state: EmotionState = None) -> str:
        """Inject emotional context into the AI system prompt."""
        state = state or self._state
        style = self.get_response_style(state.primary)
        session_vibe = self._get_session_vibe()

        injection = f"""
[EMOTIONAL INTELLIGENCE CONTEXT]
User's Current Emotion: {state.primary.upper()} (confidence: {state.confidence:.0%})
Secondary Emotion: {state.secondary or 'none'}
Valence (mood positivity): {state.valence:+.1f} | Arousal (energy): {state.arousal:.1f}
Session Overall Vibe: {session_vibe}
Recommended Tone: {style['tone']}
Response Length Style: {style['response_length']}
Start your reply with: "{style['prefix']}"

IMPORTANT: Adapt your response to match user's emotional state. 
If frustrated → be calm, direct, no lectures.
If happy → celebrate with them.
If tired → be brief and supportive.
If urgent → skip pleasantries, just execute.
"""
        return base_prompt + injection

    def _get_session_vibe(self) -> str:
        if len(self._session_mood_track) < 3:
            return "neutral"
        avg = sum(self._session_mood_track[-10:]) / len(self._session_mood_track[-10:])
        if avg > 0.4:
            return "positive/productive"
        elif avg < -0.3:
            return "negative/struggling"
        else:
            return "mixed/neutral"

    # ──────────────────────────────────────────────────────────────────────────
    # BACKGROUND MOOD ANALYSIS
    # ──────────────────────────────────────────────────────────────────────────

    def _mood_analysis_loop(self):
        """Periodically analyze long-term mood trends."""
        while True:
            time.sleep(600)  # Every 10 min
            with self._lock:
                if len(self._session_mood_track) >= 10:
                    avg_valence = sum(self._session_mood_track[-20:]) / min(len(self._session_mood_track), 20)
                    vibe = self._get_session_vibe()
                    logger.info(f"[EMOTIONAL AI] 📊 Session mood: {vibe} (avg valence: {avg_valence:+.2f})")

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def current_state(self) -> EmotionState:
        return self._state

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "current_emotion": self._state.to_dict(),
                "session_vibe": self._get_session_vibe(),
                "emotion_distribution": dict(self._emotion_counts),
                "frustration_alerts": len(self._frustration_alerts),
                "recent_emotions": [
                    h.to_dict() for h in list(self._history)[-10:]
                ],
                "avg_valence_last_20": round(
                    sum(self._session_mood_track[-20:]) / max(len(self._session_mood_track[-20:]), 1), 3
                ),
            }

    def get_emotion_history(self, limit: int = 50) -> List[dict]:
        with self._lock:
            return [h.to_dict() for h in list(self._history)[-limit:]]


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[EmotionalIntelligenceEngine] = None
_lock = threading.Lock()

def get_emotional_engine() -> EmotionalIntelligenceEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = EmotionalIntelligenceEngine()
    return _instance
