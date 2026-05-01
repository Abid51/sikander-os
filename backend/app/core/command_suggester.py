"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS COMMAND SUGGESTER — Intelligent autocomplete & prediction
  Real: frequency ranking, recency decay, fuzzy matching, LLM fallback
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import os
import time
import re
import difflib
import threading
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Built-in command registry ─────────────────────────────────────────────────

SYSTEM_COMMANDS: Dict[str, List[str]] = {
    "system": [
        "Show system stats",
        "List processes",
        "Check memory usage",
        "Monitor CPU",
        "Show disk space",
        "List files in directory",
        "Restart system",
        "Check GPU usage",
        "Show network stats",
    ],
    "ai": [
        "Ask IGRIS a question",
        "Modify code",
        "Generate content",
        "Analyze document",
        "Summarize text",
        "Translate text",
        "Write an article",
        "Explain this code",
        "Debug this error",
    ],
    "voice": [
        "Enable voice control",
        "Disable voice control",
        "Change language",
        "Switch to Urdu",
        "Switch to English",
        "Set voice speed",
        "Record voice command",
    ],
    "admin": [
        "Show admin panel",
        "View logs",
        "Check cloud status",
        "Restart backend",
        "View analytics",
        "Clear cache",
        "Export data",
        "Backup system",
    ],
    "file": [
        "Open file",
        "Create file",
        "Delete file",
        "Copy file",
        "Rename file",
        "Search files",
        "Compress files",
        "Upload to cloud",
    ],
    "daemon": [
        "List active daemons",
        "Start StormCaller task",
        "VoidWalker file operations",
        "DataDrake analyze data",
        "IronCrown hardware status",
        "Chronos schedule event",
        "Show daemon health",
    ],
    "workflow": [
        "Create workflow",
        "Run workflow",
        "List workflows",
        "Schedule job",
        "Cancel running job",
        "Show job history",
    ]
}

# Flat list for fuzzy matching
_ALL_COMMANDS: List[str] = [cmd for cmds in SYSTEM_COMMANDS.values() for cmd in cmds]


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class CommandRecord:
    command: str
    category: str
    frequency: int = 0
    success_count: int = 0
    fail_count: int = 0
    total_time_ms: float = 0.0
    last_used_ts: float = field(default_factory=time.time)

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 1.0

    @property
    def avg_time_ms(self) -> float:
        total = self.success_count + self.fail_count
        return self.total_time_ms / total if total > 0 else 0.0


class CommandSuggester:
    """
    Intelligent command suggestion engine with:
    - Frequency + recency scoring
    - Fuzzy prefix matching (difflib)
    - LLM fallback for natural language suggestions
    - Persistent JSON history
    - Per-command analytics
    """

    PERSIST_FILE = os.path.join(
        os.path.dirname(__file__), "..", "..", "command_history.json"
    )
    MAX_HISTORY_ENTRIES = 5000

    def __init__(self, max_history: int = 5000):
        self.max_history = max_history
        self._lock = threading.RLock()
        self._records: Dict[str, CommandRecord] = {}  # command → record
        self._history: List[Dict] = []                # ordered timeline
        self._session_buffer: List[str] = []          # last N commands (sequence detection)
        self._sequence_counts: Dict[str, Counter] = defaultdict(Counter)  # cmd → next_cmd_counter
        self._load()
        logger.info(f"[COMMAND SUGGESTER] ⚡ Online — {len(self._records)} commands in memory.")

    # ── Record ────────────────────────────────────────────────────────────────

    def add_to_history(
        self,
        command: str,
        success: bool,
        execution_time_ms: float = 0.0,
        category: Optional[str] = None
    ) -> None:
        """Record command execution"""
        cat = category or self._get_command_type(command)
        now = time.time()

        with self._lock:
            if command not in self._records:
                self._records[command] = CommandRecord(command=command, category=cat)
            rec = self._records[command]
            rec.frequency += 1
            rec.last_used_ts = now
            rec.total_time_ms += execution_time_ms
            if success:
                rec.success_count += 1
            else:
                rec.fail_count += 1

            # Timeline
            self._history.append({
                "command":       command,
                "category":      cat,
                "success":       success,
                "execution_time_ms": execution_time_ms,
                "timestamp":     datetime.now().isoformat()
            })
            if len(self._history) > self.MAX_HISTORY_ENTRIES:
                self._history.pop(0)

            # Sequence learning
            if self._session_buffer:
                prev = self._session_buffer[-1]
                self._sequence_counts[prev][command] += 1
            self._session_buffer.append(command)
            if len(self._session_buffer) > 50:
                self._session_buffer.pop(0)

        # Auto-save every 20 commands
        if len(self._history) % 20 == 0:
            threading.Thread(target=self._save, daemon=True).start()

    # ── Suggestions ───────────────────────────────────────────────────────────

    def get_suggestions(
        self,
        partial_command: str,
        limit: int = 8,
        include_history: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Rank suggestions using:
        1. Exact prefix match (highest priority)
        2. Fuzzy similarity (difflib)
        3. Frequency + recency score
        4. Recent history
        """
        partial_lower = partial_command.lower().strip()
        suggestions: Dict[str, Dict] = {}

        # --- 1. Prefix matches from built-in commands ---
        for cmd in _ALL_COMMANDS:
            if cmd.lower().startswith(partial_lower):
                score = 0.95
                suggestions[cmd] = {
                    "command": cmd,
                    "score":   score,
                    "type":    self._get_command_type(cmd),
                    "match":   "prefix"
                }

        # --- 2. Fuzzy matches ---
        if partial_lower:
            fuzzy = difflib.get_close_matches(
                partial_lower,
                [c.lower() for c in _ALL_COMMANDS],
                n=limit * 2,
                cutoff=0.4
            )
            for match_lower in fuzzy:
                cmd = next((c for c in _ALL_COMMANDS if c.lower() == match_lower), match_lower)
                if cmd not in suggestions:
                    suggestions[cmd] = {
                        "command": cmd,
                        "score":   0.6,
                        "type":    self._get_command_type(cmd),
                        "match":   "fuzzy"
                    }

        # --- 3. User history commands ---
        if include_history:
            with self._lock:
                user_cmds = sorted(
                    self._records.values(),
                    key=lambda r: self._score(r),
                    reverse=True
                )
            for rec in user_cmds[:20]:
                cmd = rec.command
                if partial_lower and partial_lower not in cmd.lower():
                    continue
                if cmd not in suggestions:
                    suggestions[cmd] = {
                        "command":      cmd,
                        "score":        self._score(rec),
                        "type":         rec.category,
                        "match":        "history",
                        "frequency":    rec.frequency,
                        "success_rate": round(rec.success_rate, 2)
                    }
                else:
                    # Boost if also in history
                    suggestions[cmd]["score"] = min(suggestions[cmd]["score"] + 0.1, 1.0)
                    suggestions[cmd]["frequency"] = rec.frequency
                    suggestions[cmd]["success_rate"] = round(rec.success_rate, 2)

        # Sort by score
        ranked = sorted(suggestions.values(), key=lambda s: s["score"], reverse=True)
        return ranked[:limit]

    def get_next_likely_commands(self, after_command: str, top_k: int = 3) -> List[Dict]:
        """Predict next command based on sequence patterns"""
        with self._lock:
            next_counts = self._sequence_counts.get(after_command, Counter())
        if not next_counts:
            return []
        total = sum(next_counts.values())
        return [
            {
                "command":     cmd,
                "probability": round(count / total, 2),
                "times_seen":  count
            }
            for cmd, count in next_counts.most_common(top_k)
        ]

    async def get_llm_suggestions(self, user_input: str, limit: int = 5) -> List[Dict]:
        """LLM-powered command suggestions for natural language input"""
        commands_str = "\n".join(f"- {c}" for c in _ALL_COMMANDS[:40])
        try:
            from app.core.llm_manager import universal_llm
            raw = await universal_llm.generate_response(
                system_prompt=(
                    "You are Igris command suggester. Given user input, suggest the most relevant commands. "
                    f"Available commands:\n{commands_str}\n"
                    f"Return ONLY JSON array: [{{\"command\": \"...\", \"reason\": \"...\"}}] (max {limit} items)"
                ),
                user_prompt=f"User typed: {user_input}",
                is_json=True,
                max_tokens=300
            )
            suggestions = json.loads(raw)
            return suggestions[:limit]
        except Exception as e:
            logger.debug(f"[COMMAND SUGGESTER] LLM fallback: {e}")
            return self.get_suggestions(user_input, limit=limit)

    # ── Analytics ─────────────────────────────────────────────────────────────

    def get_frequently_used(self, limit: int = 10) -> List[Dict]:
        with self._lock:
            top = sorted(self._records.values(), key=lambda r: r.frequency, reverse=True)
        return [
            {
                "command":      r.command,
                "frequency":    r.frequency,
                "success_rate": round(r.success_rate, 2),
                "avg_time_ms":  round(r.avg_time_ms, 1),
                "last_used":    datetime.fromtimestamp(r.last_used_ts).isoformat()
            }
            for r in top[:limit]
        ]

    def search_history(self, query: str, limit: int = 10) -> List[Dict]:
        with self._lock:
            results = [e for e in self._history if query.lower() in e["command"].lower()]
        results.sort(key=lambda x: x["timestamp"], reverse=True)
        return results[:limit]

    def get_analytics(self) -> Dict[str, Any]:
        with self._lock:
            hist = list(self._history)
            records = list(self._records.values())

        total = len(hist)
        successful = sum(1 for e in hist if e.get("success"))
        by_category: Dict[str, int] = defaultdict(int)
        for e in hist:
            by_category[e.get("category", "unknown")] += 1

        most_used = sorted(records, key=lambda r: r.frequency, reverse=True)[:10]
        worst_success = sorted(
            [r for r in records if r.frequency >= 3],
            key=lambda r: r.success_rate
        )[:5]

        return {
            "total_commands":        total,
            "successful_commands":   successful,
            "success_rate":          round(successful / total * 100, 1) if total else 100.0,
            "unique_commands":       len(records),
            "avg_execution_time_ms": round(sum(r.total_time_ms for r in records) / max(total, 1), 1),
            "commands_by_category":  dict(by_category),
            "most_used_commands":    [{"command": r.command, "frequency": r.frequency} for r in most_used],
            "worst_success_rate":    [{"command": r.command, "rate": round(r.success_rate, 2)} for r in worst_success],
            "sequence_patterns":     {
                cmd: dict(counter.most_common(3))
                for cmd, counter in list(self._sequence_counts.items())[:10]
            }
        }

    def get_command_categories(self) -> Dict[str, List[str]]:
        return SYSTEM_COMMANDS

    def get_quick_reference(self) -> Dict[str, List[str]]:
        return SYSTEM_COMMANDS

    # ── Scoring ───────────────────────────────────────────────────────────────

    def _score(self, rec: CommandRecord) -> float:
        """Frequency × recency decay × success rate"""
        freq_score = min(rec.frequency / 20, 1.0)
        days_since = (time.time() - rec.last_used_ts) / 86400
        recency_score = max(0.0, 1.0 - days_since / 30)
        return freq_score * 0.5 + recency_score * 0.3 + rec.success_rate * 0.2

    def _get_command_type(self, command: str) -> str:
        for category, cmds in SYSTEM_COMMANDS.items():
            if command in cmds:
                return category
        return "custom"

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self) -> None:
        try:
            data = {
                "records": {
                    cmd: {
                        "frequency":    r.frequency,
                        "success_count": r.success_count,
                        "fail_count":   r.fail_count,
                        "total_time_ms": r.total_time_ms,
                        "last_used_ts": r.last_used_ts,
                        "category":     r.category
                    }
                    for cmd, r in self._records.items()
                },
                "history": self._history[-500:],  # persist last 500
            }
            os.makedirs(os.path.dirname(os.path.abspath(self.PERSIST_FILE)), exist_ok=True)
            with open(self.PERSIST_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug(f"[COMMAND SUGGESTER] Save error: {e}")

    def _load(self) -> None:
        if not os.path.exists(self.PERSIST_FILE):
            return
        try:
            with open(self.PERSIST_FILE) as f:
                data = json.load(f)
            for cmd, rd in data.get("records", {}).items():
                self._records[cmd] = CommandRecord(
                    command=cmd,
                    category=rd.get("category", "custom"),
                    frequency=rd.get("frequency", 0),
                    success_count=rd.get("success_count", 0),
                    fail_count=rd.get("fail_count", 0),
                    total_time_ms=rd.get("total_time_ms", 0.0),
                    last_used_ts=rd.get("last_used_ts", time.time())
                )
            self._history = data.get("history", [])
            logger.info(f"[COMMAND SUGGESTER] Loaded {len(self._records)} records from disk.")
        except Exception as e:
            logger.warning(f"[COMMAND SUGGESTER] Load error: {e}")


# ── Singleton ─────────────────────────────────────────────────────────────────

command_suggester = CommandSuggester()
