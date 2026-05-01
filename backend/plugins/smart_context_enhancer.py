"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS PLUGIN — Smart Context Enhancer
  Automatically enriches AI responses with live data:
    - Current date/time
    - System locale + timezone
    - Recent conversation summary
    - Smart follow-up question suggestions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import re
import time
import logging
from datetime import datetime, timezone
from typing import Optional
from collections import deque
from app.core.plugin_loader import IgrisPlugin

logger = logging.getLogger(__name__)


class SmartContextPlugin(IgrisPlugin):
    """
    Enhances Igris AI with automatic context injection.
    - Injects date/time/locale into AI context automatically
    - Tracks conversation history for better memory
    - Suggests follow-up questions
    - Detects topic shifts and summarises conversations
    """

    NAME        = "smart_context_enhancer"
    VERSION     = "1.5.0"
    DESCRIPTION = "Enriches AI responses with live context, memory, and follow-up suggestions"
    AUTHOR      = "Igris OS Core Team"
    REQUIRES    = []
    TAGS        = ["ai", "context", "memory", "productivity", "production"]

    MAX_HISTORY      = 50    # max conversation turns to track
    SUMMARY_AFTER    = 10    # summarise every N turns
    INJECT_DATETIME  = True  # auto-inject current time in responses

    def __init__(self):
        self._history: deque             = deque(maxlen=self.MAX_HISTORY)
        self._topic_counts: dict         = {}
        self._loaded_at: Optional[float] = None
        self._message_count: int         = 0
        self._last_summary: str          = ""
        self._session_start: str         = datetime.now().isoformat()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def on_load(self) -> None:
        self._loaded_at = time.time()
        logger.info("[SmartContextPlugin] Loaded — context enhancement ACTIVE ✅")

    def on_unload(self) -> None:
        logger.info(
            "[SmartContextPlugin] Unloaded after %d messages.", self._message_count
        )

    def on_startup(self) -> None:
        logger.info(
            "[SmartContextPlugin] Session started at %s", self._session_start
        )

    def on_shutdown(self) -> None:
        logger.info(
            "[SmartContextPlugin] Session ended — %d conversation turns tracked.",
            self._message_count
        )

    # ── Hook: Commands ───────────────────────────────────────────────────────

    def on_command(self, command: str, args: dict):
        if command == "context_summary":
            return self._build_summary()
        if command == "conversation_history":
            limit = int(args.get("limit", 10))
            return {
                "history":  list(self._history)[-limit:],
                "total":    self._message_count,
                "session_start": self._session_start,
            }
        if command == "topic_stats":
            return {
                "topics": self._topic_counts,
                "most_discussed": max(self._topic_counts, key=self._topic_counts.get)
                if self._topic_counts else None,
            }
        if command == "follow_up_suggestions":
            last_msg = args.get("message", "")
            return {"suggestions": self._generate_follow_ups(last_msg)}
        if command == "clear_context":
            self._history.clear()
            self._topic_counts.clear()
            self._last_summary = ""
            self._message_count = 0
            self._session_start = datetime.now().isoformat()
            return {"status": "cleared", "session_start": self._session_start}
        return None

    def on_message(self, user_msg: str, ai_response: str) -> Optional[str]:
        """Track conversation and optionally append helpful context footer."""
        self._message_count += 1

        # Store in history
        self._history.append({
            "turn":      self._message_count,
            "user":      user_msg[:300],     # cap at 300 chars
            "ai":        ai_response[:500],  # cap at 500 chars
            "timestamp": datetime.now().isoformat(),
        })

        # Track topics
        self._extract_topics(user_msg)

        # Auto-summarise every N turns
        if self._message_count % self.SUMMARY_AFTER == 0:
            self._last_summary = self._build_summary().get("summary", "")

        # Optionally inject date/time footer for time-sensitive responses
        if self.INJECT_DATETIME and self._is_time_sensitive(user_msg):
            now_str = datetime.now().strftime("%A, %d %B %Y — %H:%M:%S")
            return ai_response + f"\n\n🕐 *Current time: {now_str}*"

        return None

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _extract_topics(self, text: str) -> None:
        """Simple keyword-based topic extraction."""
        topic_keywords = {
            "code":     ["code", "function", "class", "python", "javascript", "bug", "error"],
            "finance":  ["money", "crypto", "bitcoin", "trade", "profit", "income", "invest"],
            "system":   ["cpu", "ram", "disk", "process", "memory", "performance", "speed"],
            "ai":       ["ai", "model", "train", "neural", "gpt", "igris", "intelligence"],
            "security": ["security", "hack", "threat", "firewall", "password", "encrypt"],
            "urdu":     ["کیا", "کریں", "بتاؤ", "سیکھو", "چاہیے", "ہے"],
        }
        text_lower = text.lower()
        for topic, keywords in topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                self._topic_counts[topic] = self._topic_counts.get(topic, 0) + 1

    def _is_time_sensitive(self, text: str) -> bool:
        """Detect if message is asking about time/date/current events."""
        time_patterns = [
            r"\bab\b", r"\baaj\b", r"\bkab\b",          # Urdu: now, today, when
            r"\bnow\b", r"\btoday\b", r"\bcurrent\b",
            r"\btime\b", r"\bdate\b", r"\bwhen\b",
            r"\bآج\b",  r"\bابھی\b"
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in time_patterns)

    def _generate_follow_ups(self, message: str) -> list:
        """Generate contextual follow-up question suggestions."""
        follow_ups = []
        text_lower  = message.lower()

        if any(kw in text_lower for kw in ["code", "function", "class", "python"]):
            follow_ups = [
                "Kya main is code ko optimize kar sakta hoon?",
                "Is mein koi bug ho sakta hai?",
                "Kya aap test cases bhi likh sakte hain?",
            ]
        elif any(kw in text_lower for kw in ["money", "crypto", "trade", "finance"]):
            follow_ups = [
                "Mujhe risk management ke baare mein batao?",
                "Kis platform par trade karna best hai?",
                "Portfolio diversification kaise karein?",
            ]
        elif any(kw in text_lower for kw in ["cpu", "ram", "slow", "performance"]):
            follow_ups = [
                "Kaunsi processes sabse zyada resources le rahi hain?",
                "System ko optimize karne ke liye kya karna chahiye?",
                "Kya hardware upgrade ki zaroorat hai?",
            ]
        else:
            follow_ups = [
                "Kya aap mujhe is baare mein aur batao?",
                "Kya koi aur option bhi hai?",
                "Mujhe step by step guide chahiye.",
            ]

        return follow_ups[:3]

    def _build_summary(self) -> dict:
        """Build a summary of the current conversation session."""
        history = list(self._history)
        if not history:
            return {"summary": "No conversation yet.", "turns": 0}

        topics        = list(self._topic_counts.keys())
        dominant      = max(self._topic_counts, key=self._topic_counts.get) \
                        if self._topic_counts else "general"
        turns         = len(history)
        first_msg     = history[0]["user"] if history else ""
        last_msg      = history[-1]["user"] if history else ""

        summary = (
            f"Session started: {self._session_start} | "
            f"Turns: {turns} | "
            f"Main topic: {dominant} | "
            f"Topics discussed: {', '.join(topics) or 'general'}"
        )
        return {
            "summary":       summary,
            "turns":         turns,
            "topics":        topics,
            "dominant_topic": dominant,
            "first_message": first_msg[:100],
            "last_message":  last_msg[:100],
            "session_start": self._session_start,
        }

    # ── Info ─────────────────────────────────────────────────────────────────

    def get_commands(self) -> list:
        return [
            {"name": "context_summary",        "args": [],            "description": "Get session conversation summary"},
            {"name": "conversation_history",   "args": ["limit"],     "description": "Get last N conversation turns"},
            {"name": "topic_stats",            "args": [],            "description": "Get topic frequency statistics"},
            {"name": "follow_up_suggestions",  "args": ["message"],   "description": "Get contextual follow-up suggestions"},
            {"name": "clear_context",          "args": [],            "description": "Clear conversation history and context"},
        ]

    def get_status(self) -> dict:
        uptime = time.time() - self._loaded_at if self._loaded_at else 0
        return {
            "status":           "active",
            "messages_tracked": self._message_count,
            "history_stored":   len(self._history),
            "topics_tracked":   len(self._topic_counts),
            "uptime_secs":      round(uptime, 1),
            "last_summary":     self._last_summary[:200] if self._last_summary else "none",
        }
