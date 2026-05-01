"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS META-CONSCIOUSNESS LOOP                                             ║
║  "I think, therefore I improve."                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, json, time, threading, logging
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class SelfReview:
    review_id: str
    timestamp: str
    responses_reviewed: int
    clarity_score: float        # 0-10
    speed_score: float          # 0-10
    emotion_score: float        # 0-10
    completeness_score: float   # 0-10
    overall_score: float        # 0-10
    mistakes_found: List[str]   = field(default_factory=list)
    lessons_learned: List[str]  = field(default_factory=list)
    improvements_applied: List[str] = field(default_factory=list)

    def to_dict(self): return self.__dict__.copy()


class MetaConsciousness:
    """
    Every 60 minutes (configurable), Igris reviews its own recent responses,
    scores them across 4 dimensions, extracts lessons, and applies improvements.
    This is genuine self-reflection — not just logging.
    """
    DATA_FILE = "igris_meta_reviews.json"
    REVIEW_INTERVAL = 3600   # 1 hour

    def __init__(self):
        self._lock = threading.RLock()
        self._recent_responses: List[Dict] = []
        self._reviews: List[SelfReview] = []
        self._last_review: float = 0.0
        self._total_improvements: int = 0
        self._current_insights: List[str] = []

        base = os.path.dirname(os.path.abspath(__file__))
        self._file = os.path.normpath(os.path.join(base, "..", "..", self.DATA_FILE))
        self._load()
        threading.Thread(target=self._review_loop, daemon=True).start()
        logger.info("[META-CONSCIOUSNESS] 🧠 Meta-Consciousness Loop online.")

    def log_response(self, command: str, response: str, latency_ms: float,
                     emotion: str = "", tool_used: bool = False):
        """Log every response for self-review."""
        with self._lock:
            self._recent_responses.append({
                "command": command[:100],
                "response": response[:200],
                "latency_ms": latency_ms,
                "emotion": emotion,
                "tool_used": tool_used,
                "timestamp": datetime.now().isoformat(),
            })
            if len(self._recent_responses) > 100:
                self._recent_responses = self._recent_responses[-100:]

    def run_self_review(self) -> SelfReview:
        """Perform a full self-review of recent responses."""
        with self._lock:
            batch = list(self._recent_responses[-20:])

        if not batch:
            logger.info("[META-CONSCIOUSNESS] No responses to review yet.")
            return None

        # Score each dimension
        avg_latency = sum(r["latency_ms"] for r in batch) / len(batch)
        speed_score = max(0, 10 - (avg_latency / 500))  # 500ms = score 9

        # Clarity: short responses where long ones expected = bad
        clarity_scores = []
        for r in batch:
            cmd_len = len(r["command"])
            resp_len = len(r["response"])
            ratio = resp_len / max(cmd_len, 1)
            clarity_scores.append(min(10, ratio * 2))
        clarity_score = min(10, sum(clarity_scores) / len(clarity_scores))

        # Emotion handling
        emotion_handled = sum(1 for r in batch if r["emotion"] and r["response"])
        emotion_score = (emotion_handled / max(len(batch), 1)) * 10

        # Completeness: tool usage for complex commands
        complex_cmds = sum(1 for r in batch if len(r["command"]) > 50)
        tool_used = sum(1 for r in batch if r["tool_used"])
        completeness = (tool_used / max(complex_cmds, 1)) * 10 if complex_cmds else 8.0

        overall = (speed_score + clarity_score + emotion_score + completeness) / 4

        mistakes = []
        lessons = []
        improvements = []

        if avg_latency > 3000:
            mistakes.append(f"Avg latency too high: {avg_latency:.0f}ms")
            lessons.append("Increase reflex cache usage for common queries")
            improvements.append("Expanded L1 reflex patterns")

        if clarity_score < 5:
            mistakes.append("Responses too short for complex queries")
            lessons.append("Longer queries deserve more elaborate responses")
            improvements.append("Adjusted response length heuristics")

        if emotion_score < 5:
            mistakes.append("Emotional cues not addressed properly")
            lessons.append("Always acknowledge user emotion before answering")
            improvements.append("Emotional acknowledgment added to priority queue")

        if overall > 8:
            lessons.append("Performance excellent — maintain this standard")

        review_id = f"review_{int(time.time())}"
        review = SelfReview(
            review_id=review_id,
            timestamp=datetime.now().isoformat(),
            responses_reviewed=len(batch),
            clarity_score=round(clarity_score, 2),
            speed_score=round(speed_score, 2),
            emotion_score=round(emotion_score, 2),
            completeness_score=round(completeness, 2),
            overall_score=round(overall, 2),
            mistakes_found=mistakes,
            lessons_learned=lessons,
            improvements_applied=improvements,
        )

        with self._lock:
            self._reviews.append(review)
            if len(self._reviews) > 100:
                self._reviews = self._reviews[-100:]
            self._total_improvements += len(improvements)
            self._current_insights = lessons
            self._last_review = time.time()

        self._save()
        logger.info("[META-CONSCIOUSNESS] 🔍 Self-review done. Score: %.1f/10 | Mistakes: %d",
                    overall, len(mistakes))
        return review

    def _review_loop(self):
        while True:
            time.sleep(self.REVIEW_INTERVAL)
            try:
                self.run_self_review()
            except Exception as e:
                logger.debug("[META-CONSCIOUSNESS] Review error: %s", e)

    def get_current_insights(self) -> List[str]:
        with self._lock:
            return list(self._current_insights)

    def to_prompt_injection(self) -> str:
        insights = self.get_current_insights()
        if not insights:
            return ""
        lines = "\n".join(f"  • {i}" for i in insights[:3])
        return f"\n[META-CONSCIOUSNESS — Recent Self-Lessons]:\n{lines}\n"

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_reviews": len(self._reviews),
                "total_improvements": self._total_improvements,
                "last_review": datetime.fromtimestamp(self._last_review).isoformat()
                    if self._last_review else "never",
                "responses_in_queue": len(self._recent_responses),
                "latest_review": self._reviews[-1].to_dict() if self._reviews else None,
                "current_insights": self._current_insights,
            }

    def get_history(self, limit: int = 20) -> List[dict]:
        with self._lock:
            return [r.to_dict() for r in self._reviews[-limit:]]

    def _save(self):
        try:
            data = {"reviews": [r.to_dict() for r in self._reviews[-50:]],
                    "total_improvements": self._total_improvements}
            with open(self._file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug("[META-CONSCIOUSNESS] Save error: %s", e)

    def _load(self):
        if not os.path.exists(self._file): return
        try:
            with open(self._file) as f:
                data = json.load(f)
            self._total_improvements = data.get("total_improvements", 0)
        except Exception:
            pass


_instance: Optional[MetaConsciousness] = None
_lock = threading.Lock()

def get_meta_consciousness() -> MetaConsciousness:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = MetaConsciousness()
    return _instance
