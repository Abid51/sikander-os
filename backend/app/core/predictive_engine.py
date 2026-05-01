"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         IGRIS PREDICTIVE TASK ENGINE                                       ║
║         "I know what you need before you ask."                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import time
import json
import math
import threading
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter, deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#                          DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PatternRecord:
    """A learned behavioral pattern."""
    pattern_id: str
    pattern_type: str   # time_based | sequence | frequency | context
    trigger: dict       # e.g. {"hour": 20, "weekday": "Monday"}
    action: str
    action_params: dict
    confidence: float
    occurrences: int
    last_seen: str
    description: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Prediction:
    """A predicted action Igris should take."""
    prediction_id: str
    action: str
    action_params: dict
    reason: str
    confidence: float
    predicted_at: str = field(default_factory=lambda: datetime.now().isoformat())
    executed: bool = False
    outcome: Optional[str] = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# ═══════════════════════════════════════════════════════════════════════════════
#                      PREDICTIVE TASK ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class PredictiveTaskEngine:
    """
    Igris Predictive Task Engine.

    Learns user behavior patterns and proactively executes tasks:
    ─────────────────────────────────────────────────────────────
    1. Time-based patterns (every Monday 9AM → open VS Code)
    2. Sequence patterns (user opens Spotify → dim screen)
    3. Frequency patterns (user runs X command often → suggest shortcut)
    4. Context patterns (when battery < 20% → close Chrome)
    5. Pre-loading (learn what files user opens after what)
    6. Smart scheduling (run heavy tasks when CPU < 15%)
    """

    MIN_OCCURRENCES = 3          # Min times a pattern must occur before acting
    CONFIDENCE_THRESHOLD = 0.65  # Min confidence to auto-execute
    LEARNING_WINDOW_DAYS = 30
    PATTERN_FILE = "igris_patterns.json"
    CHECK_INTERVAL = 60          # seconds between prediction checks

    def __init__(self, action_executor: Optional[Callable] = None):
        """
        action_executor: async callable that takes (action_name, params) and executes it.
        If None, predictions are logged but not auto-executed.
        """
        self.action_executor = action_executor
        self._lock = threading.RLock()

        # Learning stores
        self._command_log: deque = deque(maxlen=5000)
        self._hourly_commands: Dict[int, Counter] = defaultdict(Counter)       # hour → Counter(commands)
        self._weekday_commands: Dict[str, Counter] = defaultdict(Counter)      # weekday → Counter(commands)
        self._sequence_buffer: deque = deque(maxlen=20)                        # Recent commands for sequence detection
        self._app_sequences: Dict[str, Counter] = defaultdict(Counter)         # after_app → what_opens_next
        self._learned_patterns: Dict[str, PatternRecord] = {}
        self._prediction_history: deque = deque(maxlen=200)

        # Load persisted patterns
        self._patterns_file = os.path.join(
            os.path.dirname(__file__), "..", "..", self.PATTERN_FILE
        )
        self._load_patterns()

        # Start prediction loop
        threading.Thread(target=self._prediction_loop, daemon=True).start()
        logger.info("[PREDICTIVE ENGINE] 🔮 Predictive Task Engine activated.")

    # ──────────────────────────────────────────────────────────────────────────
    # OBSERVATION (Learning)
    # ──────────────────────────────────────────────────────────────────────────

    def observe_command(self, command: str, metadata: Dict[str, Any] = None):
        """
        Feed a user command to the learning engine.
        Call this every time the user sends a command to Igris.
        """
        now = datetime.now()
        entry = {
            "command": command,
            "timestamp": now.isoformat(),
            "hour": now.hour,
            "weekday": now.strftime("%A"),
            "minute": now.minute,
            "metadata": metadata or {},
        }

        with self._lock:
            self._command_log.append(entry)
            self._hourly_commands[now.hour][command] += 1
            self._weekday_commands[now.strftime("%A")][command] += 1

            # Sequence learning
            self._sequence_buffer.append(command)
            self._learn_sequences()

        # Periodically extract patterns
        if len(self._command_log) % 20 == 0:
            threading.Thread(target=self._extract_patterns, daemon=True).start()

    def observe_app_opened(self, app_name: str):
        """Observe which applications are opened (for sequence prediction)."""
        with self._lock:
            if self._sequence_buffer:
                prev = list(self._sequence_buffer)[-1]
                self._app_sequences[prev][app_name] += 1
            self._sequence_buffer.append(f"open:{app_name}")

    # ──────────────────────────────────────────────────────────────────────────
    # PATTERN EXTRACTION
    # ──────────────────────────────────────────────────────────────────────────

    def _learn_sequences(self):
        """Detect A→B command sequences."""
        seq = list(self._sequence_buffer)
        if len(seq) < 2:
            return
        for i in range(len(seq) - 1):
            a, b = seq[i], seq[i + 1]
            key = f"seq:{a}→{b}"
            if key in self._learned_patterns:
                self._learned_patterns[key].occurrences += 1
                self._learned_patterns[key].last_seen = datetime.now().isoformat()
                conf = min(self._learned_patterns[key].occurrences / 10, 1.0)
                self._learned_patterns[key].confidence = conf
            else:
                self._learned_patterns[key] = PatternRecord(
                    pattern_id=key,
                    pattern_type="sequence",
                    trigger={"after_command": a},
                    action=b,
                    action_params={},
                    confidence=0.1,
                    occurrences=1,
                    last_seen=datetime.now().isoformat(),
                    description=f"After '{a[:40]}', user often does '{b[:40]}'",
                )

    def _extract_patterns(self):
        """Extract time-based and frequency patterns from command logs."""
        with self._lock:
            # Time-based patterns
            for hour, counter in self._hourly_commands.items():
                for cmd, count in counter.most_common(3):
                    if count >= self.MIN_OCCURRENCES:
                        key = f"time:{hour}:{cmd[:30]}"
                        confidence = min(count / 10, 0.95)
                        if key not in self._learned_patterns:
                            self._learned_patterns[key] = PatternRecord(
                                pattern_id=key,
                                pattern_type="time_based",
                                trigger={"hour": hour},
                                action=cmd,
                                action_params={},
                                confidence=confidence,
                                occurrences=count,
                                last_seen=datetime.now().isoformat(),
                                description=f"At hour {hour}:00, user often says: '{cmd[:50]}'",
                            )
                        else:
                            self._learned_patterns[key].confidence = confidence
                            self._learned_patterns[key].occurrences = count

            # Weekday patterns
            for weekday, counter in self._weekday_commands.items():
                for cmd, count in counter.most_common(2):
                    if count >= self.MIN_OCCURRENCES:
                        key = f"weekday:{weekday}:{cmd[:30]}"
                        if key not in self._learned_patterns:
                            self._learned_patterns[key] = PatternRecord(
                                pattern_id=key,
                                pattern_type="time_based",
                                trigger={"weekday": weekday},
                                action=cmd,
                                action_params={},
                                confidence=min(count / 8, 0.9),
                                occurrences=count,
                                last_seen=datetime.now().isoformat(),
                                description=f"Every {weekday}, user often says: '{cmd[:50]}'",
                            )

        self._save_patterns()

    # ──────────────────────────────────────────────────────────────────────────
    # PREDICTION
    # ──────────────────────────────────────────────────────────────────────────

    def _prediction_loop(self):
        """Background loop that generates real-time predictions."""
        while True:
            time.sleep(self.CHECK_INTERVAL)
            try:
                predictions = self.generate_predictions()
                for pred in predictions:
                    if pred.confidence >= self.CONFIDENCE_THRESHOLD and self.action_executor:
                        logger.info(f"[PREDICTIVE ENGINE] 🎯 Auto-executing: {pred.action[:60]} (conf={pred.confidence:.0%})")
                        pred.executed = True
                        # Execute in background
                        threading.Thread(
                            target=self._safe_execute,
                            args=(pred,),
                            daemon=True
                        ).start()
                    else:
                        logger.info(f"[PREDICTIVE ENGINE] 💭 Prediction (not auto-exec): {pred.reason}")
                    with self._lock:
                        self._prediction_history.append(pred)
            except Exception as e:
                logger.debug(f"[PREDICTIVE ENGINE] Loop error: {e}")

    def _safe_execute(self, pred: Prediction):
        try:
            if self.action_executor:
                self.action_executor(pred.action, pred.action_params)
                pred.outcome = "success"
        except Exception as e:
            pred.outcome = f"error: {e}"
            logger.warning(f"[PREDICTIVE ENGINE] Execution failed: {e}")

    def generate_predictions(self) -> List[Prediction]:
        """Generate a list of current time-relevant predictions."""
        now = datetime.now()
        predictions: List[Prediction] = []

        with self._lock:
            for pid, pattern in self._learned_patterns.items():
                if pattern.confidence < 0.4:
                    continue

                should_predict = False
                reason = ""

                if pattern.pattern_type == "time_based":
                    trigger = pattern.trigger
                    if "hour" in trigger and trigger["hour"] == now.hour:
                        # Check we haven't predicted this in last 50 min
                        recent_preds = [p for p in self._prediction_history
                                        if p.action == pattern.action and
                                        (datetime.now() - datetime.fromisoformat(p.predicted_at)).seconds < 3000]
                        if not recent_preds:
                            should_predict = True
                            reason = f"Pattern: At {trigger['hour']}:00, you usually: '{pattern.action[:40]}'"
                    elif "weekday" in trigger and trigger["weekday"] == now.strftime("%A"):
                        should_predict = True
                        reason = f"Pattern: Every {trigger['weekday']}, you usually: '{pattern.action[:40]}'"

                if should_predict:
                    import hashlib
                    pred_id = hashlib.sha1(f"{pid}{now.hour}{now.date()}".encode()).hexdigest()[:10]
                    predictions.append(Prediction(
                        prediction_id=pred_id,
                        action=pattern.action,
                        action_params=pattern.action_params,
                        reason=reason,
                        confidence=pattern.confidence,
                    ))

        return predictions

    def get_next_likely_commands(self, after_command: str, top_k: int = 3) -> List[dict]:
        """What will user probably do next after this command?"""
        with self._lock:
            seq_key = f"seq:{after_command}→"
            relevant = {
                pid: p for pid, p in self._learned_patterns.items()
                if pid.startswith(seq_key)
            }
            if not relevant:
                return []
            top = sorted(relevant.values(), key=lambda p: p.confidence, reverse=True)[:top_k]
            return [{"action": p.action, "confidence": p.confidence, "description": p.description} for p in top]

    # ──────────────────────────────────────────────────────────────────────────
    # PERSISTENCE
    # ──────────────────────────────────────────────────────────────────────────

    def _save_patterns(self):
        try:
            data = {pid: p.to_dict() for pid, p in self._learned_patterns.items()}
            with open(self._patterns_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug(f"[PREDICTIVE ENGINE] Save failed: {e}")

    def _load_patterns(self):
        try:
            if os.path.exists(self._patterns_file):
                with open(self._patterns_file, 'r') as f:
                    data = json.load(f)
                for pid, pdata in data.items():
                    self._learned_patterns[pid] = PatternRecord(**pdata)
                logger.info(f"[PREDICTIVE ENGINE] Loaded {len(self._learned_patterns)} patterns.")
        except Exception as e:
            logger.debug(f"[PREDICTIVE ENGINE] Load failed: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────────────

    def predict(self, target: str, context: Optional[Dict[str, Any]] = None) -> dict:
        """One-shot forecast / summary (pattern-based, not a separate ML model)."""
        context = context or {}
        with self._lock:
            n_cmd = len(self._command_log)
        return {
            "target":   target,
            "confidence": 0.0 if n_cmd < self.MIN_OCCURRENCES else min(0.5 + n_cmd / 1000, 0.99),
            "commands_observed": n_cmd,
            "context":  context,
        }

    def get_stats(self) -> dict:
        with self._lock:
            top_patterns = sorted(
                self._learned_patterns.values(),
                key=lambda p: p.confidence * p.occurrences,
                reverse=True
            )[:10]
            return {
                "total_patterns": len(self._learned_patterns),
                "total_commands_observed": len(self._command_log),
                "predictions_made": len(self._prediction_history),
                "auto_executions": sum(1 for p in self._prediction_history if p.executed),
                "top_patterns": [p.to_dict() for p in top_patterns],
                "recent_predictions": [p.to_dict() for p in list(self._prediction_history)[-5:]],
            }

    def get_all_patterns(self) -> List[dict]:
        with self._lock:
            return [p.to_dict() for p in self._learned_patterns.values()]

    def delete_pattern(self, pattern_id: str) -> bool:
        with self._lock:
            if pattern_id in self._learned_patterns:
                del self._learned_patterns[pattern_id]
                self._save_patterns()
                return True
        return False


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[PredictiveTaskEngine] = None
_lock = threading.Lock()

def get_predictive_engine(action_executor=None) -> PredictiveTaskEngine:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = PredictiveTaskEngine(action_executor=action_executor)
    return _instance
