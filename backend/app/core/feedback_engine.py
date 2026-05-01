"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS USER FEEDBACK LOOP
  Thumbs up/down → memory improvement → better future responses
  Features: rating capture, memory reinforcement, pattern learning
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from app.memory.vector_memory import get_neural_memory
    _MEMORY = True
except Exception:
    get_neural_memory = None
    _MEMORY = False


# ─────────────────────────────────────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FeedbackRecord:
    feedback_id: str
    message_id: str           # ID of the chat message being rated
    user_message: str         # What user asked
    igris_response: str       # What Igris answered
    rating: int               # -1 (thumbs down), 0 (neutral), 1 (thumbs up)
    feedback_text: Optional[str]  # Optional text explanation
    model_used: str
    timestamp: float = field(default_factory=time.time)
    processed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FeedbackStats:
    total_ratings: int
    positive: int
    negative: int
    neutral: int
    positive_rate: float
    avg_rating: float
    most_liked_topics: List[str]
    most_disliked_topics: List[str]


# ─────────────────────────────────────────────────────────────────────────────
#  FEEDBACK ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class IgrisFeedbackEngine:
    """
    User feedback system that actually improves Igris over time.

    How it works:
    ─────────────
    1. User rates a response (👍 or 👎)
    2. Positive feedback → stores Q&A pair as high-importance memory
    3. Negative feedback → stores as low-importance with "avoid" tag
    4. Igris uses these memories in future to improve similar answers
    5. Analytics show what's working and what isn't
    """

    PERSIST_FILE = "igris_feedback.json"

    def __init__(self) -> None:
        self._feedback: List[FeedbackRecord] = []
        self._memory = get_neural_memory() if _MEMORY else None
        self._persist_path = os.path.join(
            os.path.dirname(__file__), "..", "..", self.PERSIST_FILE
        )
        self._persist_path = os.path.normpath(self._persist_path)
        self._load()
        logger.info(f"[FEEDBACK] Engine loaded — {len(self._feedback)} records.")

    def submit_feedback(
        self,
        user_message: str,
        igris_response: str,
        rating: int,                     # -1, 0, or 1
        message_id: Optional[str] = None,
        feedback_text: Optional[str] = None,
        model_used: str = "unknown",
    ) -> FeedbackRecord:
        """Submit feedback for a response."""
        rating = max(-1, min(1, int(rating)))
        record = FeedbackRecord(
            feedback_id=str(uuid.uuid4())[:8],
            message_id=message_id or str(uuid.uuid4())[:8],
            user_message=user_message[:500],
            igris_response=igris_response[:1000],
            rating=rating,
            feedback_text=feedback_text,
            model_used=model_used,
        )
        self._feedback.append(record)
        self._save()

        # Process: reinforce memory
        self._process_feedback(record)

        logger.info(f"[FEEDBACK] Rating {'+1' if rating > 0 else '-1' if rating < 0 else '0'} "
                    f"for message {record.message_id}")
        return record

    def _process_feedback(self, record: FeedbackRecord) -> None:
        """Reinforce or weaken memory based on feedback."""
        if not self._memory:
            return

        try:
            if record.rating > 0:
                # POSITIVE: Store as high-importance episodic memory
                self._memory.remember(
                    content=(
                        f"GOOD ANSWER EXAMPLE:\n"
                        f"Question: {record.user_message}\n"
                        f"Answer: {record.igris_response}"
                    ),
                    memory_type="episodic",
                    tags=["positive_feedback", "good_example", record.model_used],
                    importance=0.9,
                    metadata={
                        "rating": record.rating,
                        "feedback_id": record.feedback_id,
                        "source": "user_feedback",
                    },
                )

            elif record.rating < 0:
                # NEGATIVE: Store as low-importance with avoid tag
                self._memory.remember(
                    content=(
                        f"POOR ANSWER EXAMPLE (avoid this approach):\n"
                        f"Question: {record.user_message}\n"
                        f"Bad Answer: {record.igris_response}\n"
                        f"User Note: {record.feedback_text or 'User disliked this response'}"
                    ),
                    memory_type="episodic",
                    tags=["negative_feedback", "avoid_pattern", record.model_used],
                    importance=0.3,
                    metadata={
                        "rating": record.rating,
                        "feedback_id": record.feedback_id,
                        "source": "user_feedback",
                    },
                )
            record.processed = True
        except Exception as e:
            logger.error(f"[FEEDBACK] Memory reinforcement failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get feedback statistics."""
        if not self._feedback:
            return {
                "total_ratings": 0,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "positive_rate": 0.0,
                "avg_rating": 0.0,
                "most_liked_topics": [],
                "most_disliked_topics": [],
            }

        positive = sum(1 for r in self._feedback if r.rating > 0)
        negative = sum(1 for r in self._feedback if r.rating < 0)
        neutral = sum(1 for r in self._feedback if r.rating == 0)
        total = len(self._feedback)
        avg = sum(r.rating for r in self._feedback) / total

        # Extract topics from liked/disliked messages (simple keyword extraction)
        liked = [r.user_message for r in self._feedback if r.rating > 0]
        disliked = [r.user_message for r in self._feedback if r.rating < 0]

        return {
            "total_ratings": total,
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "positive_rate": round(positive / total * 100, 1) if total else 0.0,
            "avg_rating": round(avg, 2),
            "recent_positive": [r.user_message[:100] for r in self._feedback if r.rating > 0][-5:],
            "recent_negative": [r.user_message[:100] for r in self._feedback if r.rating < 0][-5:],
        }

    def get_recent_feedback(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent feedback records."""
        return [r.to_dict() for r in self._feedback[-limit:]]

    def get_feedback_context(self, query: str, limit: int = 3) -> str:
        """
        Get feedback-based context to inject into system prompt.
        Returns examples of what worked well for similar queries.
        """
        if not self._memory:
            return ""
        try:
            results = self._memory.recall(
                f"GOOD ANSWER EXAMPLE: {query}",
                top_k=limit,
                memory_type="episodic",
            )
            if not results:
                return ""
            context_parts = []
            for rec, sim in results:
                if "positive_feedback" in rec.tags and sim > 0.1:
                    context_parts.append(rec.content[:300])
            if context_parts:
                return "\n\nRelevant past successful answers:\n" + "\n---\n".join(context_parts)
        except Exception:
            pass
        return ""

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self._feedback], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[FEEDBACK] Save error: {e}")

    def _load(self) -> None:
        if not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._feedback = [FeedbackRecord(**r) for r in data]
        except Exception as e:
            logger.warning(f"[FEEDBACK] Load error (fresh start): {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[IgrisFeedbackEngine] = None


def get_feedback_engine() -> IgrisFeedbackEngine:
    global _instance
    if _instance is None:
        _instance = IgrisFeedbackEngine()
    return _instance
