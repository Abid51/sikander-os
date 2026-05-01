"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS THOUGHT CRYSTALLIZATION ENGINE                                      ║
║  "1000 memories → 1 eternal truth"                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, re, json, time, threading, logging
from typing import Dict, List, Optional
from datetime import datetime
from collections import Counter
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class CoreBelief:
    belief_id: str
    statement: str
    category: str          # personality | preference | habit | skill | relationship
    confidence: float      # 0–1
    evidence_count: int
    first_observed: str
    last_reinforced: str
    examples: List[str] = field(default_factory=list)

    def to_dict(self): return self.__dict__.copy()


BELIEF_PATTERNS = {
    "preference": [
        r"(i (?:prefer|like|love|enjoy|always use)\s+.{3,50})",
        r"((?:dark|light) mode)",
        r"((?:prefers?|likes?)\s+\w+)",
        r"(hamesha\s+\w+\s+use karta)",
        r"(pasand\s+.{3,40})",
    ],
    "habit": [
        r"((?:every|har)\s+(?:day|night|morning|evening|week|roz|raat|subah).{3,60})",
        r"(always\s+.{5,50})",
        r"(hamesha\s+.{5,50})",
        r"(routine\s*[:\-]\s*.{5,50})",
    ],
    "personality": [
        r"((?:i am|main hoon|i'm)\s+(?:a\s+)?.{5,50})",
        r"(night.?owl)",
        r"(introvert|extrovert)",
        r"(perfectionist|minimalist)",
    ],
    "skill": [
        r"((?:i know|i can|i work with|main\s+\w+\s+janta)\s+.{3,50})",
        r"(expert in\s+\w+)",
        r"(years? of experience)",
    ],
}

class ThoughtCrystallizer:
    """
    Runs every 7 days (background) or on-demand.
    Scans all conversation history & memory files,
    extracts recurring patterns → distills them into
    persistent "Core Beliefs" that permanently shape Igris's behaviour.
    """
    DATA_FILE      = "igris_beliefs.json"
    CRYSTALLIZE_INTERVAL = 7 * 24 * 3600   # weekly

    def __init__(self):
        self._lock = threading.RLock()
        self._beliefs: Dict[str, CoreBelief] = {}
        self._raw_observations: List[str] = []
        self._last_crystallize: float = 0.0

        base = os.path.dirname(os.path.abspath(__file__))
        self._file = os.path.normpath(os.path.join(base, "..", "..", self.DATA_FILE))
        self._load()
        threading.Thread(target=self._weekly_loop, daemon=True).start()
        logger.info("[CRYSTALLIZER] 💎 Thought Crystallizer online. Beliefs: %d", len(self._beliefs))

    # ─────────────────────────────────────────────────────────────────────
    # INGESTION
    # ─────────────────────────────────────────────────────────────────────

    def observe(self, text: str):
        """Feed a user message into the observation pool."""
        with self._lock:
            self._raw_observations.append(text)
            if len(self._raw_observations) > 5000:
                self._raw_observations = self._raw_observations[-5000:]

    # ─────────────────────────────────────────────────────────────────────
    # CRYSTALLIZATION
    # ─────────────────────────────────────────────────────────────────────

    def crystallize(self, min_evidence_or_prompt=2) -> "List[CoreBelief] | dict":
        """On-demand: pass a *question string* to get a dict summary; pass *int* for batch crystallization."""
        if isinstance(min_evidence_or_prompt, str):
            return {
                "query":  min_evidence_or_prompt,
                "output": f"Crystallized reflection on: {min_evidence_or_prompt[:200]}",
                "beliefs_stored": len(self._beliefs),
                "status":   "on_demand",
            }
        min_evidence = int(min_evidence_or_prompt)
        return self._crystallize_run(min_evidence)

    def _crystallize_run(self, min_evidence: int = 2) -> List[CoreBelief]:
        """Run a full crystallization pass. Returns newly formed beliefs."""
        with self._lock:
            corpus = list(self._raw_observations)

        new_beliefs: List[CoreBelief] = []
        candidate_counter: Counter = Counter()
        candidate_examples: Dict[str, List[str]] = {}
        candidate_categories: Dict[str, str] = {}

        for text in corpus:
            t = text.lower()
            for category, patterns in BELIEF_PATTERNS.items():
                for pattern in patterns:
                    for m in re.finditer(pattern, t):
                        phrase = m.group(1).strip()[:80]
                        candidate_counter[phrase] += 1
                        candidate_examples.setdefault(phrase, []).append(text[:60])
                        candidate_categories[phrase] = category

        now = datetime.now().isoformat()
        for phrase, count in candidate_counter.items():
            if count < min_evidence:
                continue
            bid = f"belief_{abs(hash(phrase)) % 999999:06d}"
            if bid in self._beliefs:
                # Reinforce existing belief
                with self._lock:
                    self._beliefs[bid].evidence_count += count
                    self._beliefs[bid].confidence = min(1.0, self._beliefs[bid].confidence + 0.05)
                    self._beliefs[bid].last_reinforced = now
            else:
                belief = CoreBelief(
                    belief_id=bid,
                    statement=phrase.capitalize(),
                    category=candidate_categories[phrase],
                    confidence=min(1.0, count / 10),
                    evidence_count=count,
                    first_observed=now,
                    last_reinforced=now,
                    examples=list(set(candidate_examples[phrase]))[:3],
                )
                with self._lock:
                    self._beliefs[bid] = belief
                new_beliefs.append(belief)

        self._save()
        self._last_crystallize = time.time()
        logger.info("[CRYSTALLIZER] 💎 Crystallized %d new beliefs from %d observations.",
                    len(new_beliefs), len(corpus))
        return new_beliefs

    # ─────────────────────────────────────────────────────────────────────
    # PROMPT INJECTION
    # ─────────────────────────────────────────────────────────────────────

    def to_prompt_axioms(self, top_k: int = 8) -> str:
        """Return top beliefs formatted for system prompt injection."""
        with self._lock:
            top = sorted(self._beliefs.values(),
                         key=lambda b: b.confidence * b.evidence_count, reverse=True)[:top_k]
        if not top:
            return ""
        lines = [f"  • [{b.category}] {b.statement} (confidence={b.confidence:.0%})" for b in top]
        return "\n[IGRIS CORE BELIEFS — Permanent Truths About User]:\n" + "\n".join(lines) + "\n"

    # ─────────────────────────────────────────────────────────────────────
    # WEEKLY LOOP
    # ─────────────────────────────────────────────────────────────────────

    def _weekly_loop(self):
        while True:
            time.sleep(3600)   # check hourly
            if time.time() - self._last_crystallize >= self.CRYSTALLIZE_INTERVAL:
                try:
                    self.crystallize()
                except Exception as e:
                    logger.debug("[CRYSTALLIZER] Error: %s", e)

    # ─────────────────────────────────────────────────────────────────────
    # PERSISTENCE
    # ─────────────────────────────────────────────────────────────────────

    def _save(self):
        try:
            with open(self._file, "w") as f:
                json.dump({bid: b.to_dict() for bid, b in self._beliefs.items()}, f, indent=2)
        except Exception as e:
            logger.debug("[CRYSTALLIZER] Save error: %s", e)

    def _load(self):
        if not os.path.exists(self._file): return
        try:
            with open(self._file) as f:
                raw = json.load(f)
            for bid, bdata in raw.items():
                self._beliefs[bid] = CoreBelief(**bdata)
        except Exception as e:
            logger.debug("[CRYSTALLIZER] Load error: %s", e)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_beliefs": len(self._beliefs),
                "observations_pool": len(self._raw_observations),
                "last_crystallized": datetime.fromtimestamp(self._last_crystallize).isoformat()
                    if self._last_crystallize else "never",
                "top_beliefs": [b.to_dict() for b in sorted(
                    self._beliefs.values(), key=lambda b: b.confidence, reverse=True)[:5]],
            }

    def get_all_beliefs(self) -> List[dict]:
        with self._lock:
            return [b.to_dict() for b in sorted(
                self._beliefs.values(), key=lambda b: b.confidence * b.evidence_count, reverse=True)]


_instance: Optional[ThoughtCrystallizer] = None
_lock = threading.Lock()

def get_crystallizer() -> ThoughtCrystallizer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ThoughtCrystallizer()
    return _instance
