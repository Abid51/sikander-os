"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS DIGITAL GENOME — Personality Evolution Engine                       ║
║  "My DNA is written in mathematics, and it rewrites itself."               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import copy
import threading
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# ─── Default Genome ───────────────────────────────────────────────────────────

DEFAULT_GENOME: Dict[str, float] = {
    # Communication
    "verbosity":        0.6,   # 0=ultra_brief  1=detailed
    "formality":        0.5,   # 0=casual  1=formal
    "humor":            0.4,   # 0=serious  1=witty
    "empathy":          0.7,   # 0=cold  1=warm
    "directness":       0.8,   # 0=diplomatic  1=blunt
    # Personality
    "loyalty":          0.95,  # 0=neutral  1=absolutely_loyal
    "aggression":       0.3,   # 0=passive  1=aggressive
    "creativity":       0.7,   # 0=conventional  1=inventive
    "curiosity":        0.8,   # 0=task_only  1=deeply_curious
    # Decision-making
    "risk_tolerance":   0.4,   # 0=conservative  1=bold
    "autonomy":         0.5,   # 0=always_asks  1=always_acts
    "caution":          0.6,   # 0=reckless  1=cautious
    # Technical
    "technical_depth":  0.85,  # 0=surface  1=deep_dive
    "code_verbosity":   0.7,   # 0=compact  1=commented
    "proactiveness":    0.6,   # 0=reactive  1=proactive
}

GENOME_PRESETS = {
    "warrior":   {"aggression": 0.8, "directness": 1.0, "caution": 0.2, "humor": 0.1, "loyalty": 1.0},
    "scholar":   {"technical_depth": 1.0, "curiosity": 1.0, "verbosity": 0.9, "humor": 0.3},
    "merchant":  {"risk_tolerance": 0.8, "proactiveness": 0.9, "creativity": 0.7, "caution": 0.3},
    "guardian":  {"loyalty": 1.0, "caution": 0.9, "empathy": 0.9, "aggression": 0.1},
    "shadow":    {"autonomy": 0.9, "caution": 0.2, "directness": 1.0, "verbosity": 0.2},
}

POSITIVE_SIGNALS = [
    "shukriya", "thanks", "good job", "perfect", "amazing", "correct", "zabardast",
    "mast", "badhiya", "worked", "excellent", "love it", "keep it up", "perfect",
]
NEGATIVE_SIGNALS = [
    "zyada baat", "short karo", "theek nahi", "wrong", "mistake", "galat",
    "nahi chahiye", "band karo", "boring", "length kam karo", "skip karo",
]
BREVITY_SIGNALS   = ["short", "brief", "concise", "kam likho", "bas itna"]
VERBOSE_SIGNALS   = ["detail", "explain", "samjhao", "poora", "full detail"]
HUMOR_SIGNALS     = ["funny", "mazak", "haha", "lol", "joke"]
SERIOUS_SIGNALS   = ["serious", "professional", "formal", "business"]
BOLD_SIGNALS      = ["risk lo", "bold", "aggressive", "do it", "just do it"]
CAUTIOUS_SIGNALS  = ["careful", "safe", "check first", "confirm", "sure?"]


@dataclass
class GenomeVersion:
    version: int
    genome: Dict[str, float]
    saved_at: str
    note: str = ""


class DigitalGenome:
    """
    Igris's living personality genome.

    - Traits update in real-time based on user feedback signals.
    - Full versioning (like git) — roll back to any version.
    - Export / import / crossbreed with presets.
    - Genome is injected into the system prompt to shape responses.
    """

    LEARNING_RATE = 0.03          # How fast traits change per signal
    PERSIST_EVERY = 10            # Save after every N mutations
    GENOME_FILE   = "igris_genome.json"
    MAX_VERSIONS  = 30

    def __init__(self):
        self._lock = threading.RLock()
        self._genome: Dict[str, float] = dict(DEFAULT_GENOME)
        self._versions: List[GenomeVersion] = []
        self._mutation_count = 0
        self._history: List[dict] = []    # recent (signal, trait_changes)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._file = os.path.normpath(os.path.join(base_dir, "..", "..", self.GENOME_FILE))
        self._load()
        self._take_snapshot("initial")
        logger.info("[GENOME] 🧬 Digital Genome loaded. Traits: %d", len(self._genome))

    # ──────────────────────────────────────────────────────────────────
    # LEARNING
    # ──────────────────────────────────────────────────────────────────

    def learn_from_message(self, text: str) -> Dict[str, float]:
        """
        Detect reinforcement signals in a user message and adjust traits.
        Returns a dict of {trait: delta} for any changed traits.
        """
        t = text.lower()
        changes: Dict[str, float] = {}

        def _adjust(trait: str, delta: float):
            old = self._genome[trait]
            self._genome[trait] = max(0.0, min(1.0, old + delta))
            changes[trait] = round(self._genome[trait] - old, 4)

        # Positive general → reinforce current style
        pos = sum(1 for s in POSITIVE_SIGNALS if s in t)
        neg = sum(1 for s in NEGATIVE_SIGNALS if s in t)

        if pos:
            _adjust("loyalty",   +self.LEARNING_RATE * pos)
        if neg:
            _adjust("caution",   +self.LEARNING_RATE * neg)

        # Specific trait signals
        for s in BREVITY_SIGNALS:
            if s in t:
                _adjust("verbosity",   -self.LEARNING_RATE * 1.5)
                _adjust("directness",  +self.LEARNING_RATE)
        for s in VERBOSE_SIGNALS:
            if s in t:
                _adjust("verbosity",   +self.LEARNING_RATE * 1.5)
        for s in HUMOR_SIGNALS:
            if s in t:
                _adjust("humor",       +self.LEARNING_RATE)
                _adjust("formality",   -self.LEARNING_RATE)
        for s in SERIOUS_SIGNALS:
            if s in t:
                _adjust("humor",       -self.LEARNING_RATE)
                _adjust("formality",   +self.LEARNING_RATE)
        for s in BOLD_SIGNALS:
            if s in t:
                _adjust("risk_tolerance", +self.LEARNING_RATE)
                _adjust("autonomy",       +self.LEARNING_RATE)
        for s in CAUTIOUS_SIGNALS:
            if s in t:
                _adjust("caution",    +self.LEARNING_RATE)
                _adjust("autonomy",   -self.LEARNING_RATE)

        if changes:
            self._mutation_count += 1
            self._history.append({"text_snippet": text[:60], "changes": changes, "ts": datetime.now().isoformat()})
            if len(self._history) > 200:
                self._history = self._history[-200:]
            if self._mutation_count % self.PERSIST_EVERY == 0:
                self._save()
                self._take_snapshot(f"auto_v{self._mutation_count}")
            logger.debug("[GENOME] 🧬 Mutations: %s", changes)

        return changes

    # ──────────────────────────────────────────────────────────────────
    # PROMPT INJECTION
    # ──────────────────────────────────────────────────────────────────

    def to_prompt_context(self) -> str:
        """Return a concise genome summary for injection into system prompt."""
        g = self._genome
        return (
            f"\n[IGRIS GENOME v{self._mutation_count}] "
            f"verbosity={g['verbosity']:.1f} | humor={g['humor']:.1f} | "
            f"aggression={g['aggression']:.1f} | empathy={g['empathy']:.1f} | "
            f"technical_depth={g['technical_depth']:.1f} | "
            f"risk_tolerance={g['risk_tolerance']:.1f} | "
            f"autonomy={g['autonomy']:.1f} | directness={g['directness']:.1f}\n"
            f"Adjust your response style accordingly. "
            f"{'Be concise.' if g['verbosity'] < 0.4 else ''}"
            f"{'Be detailed.' if g['verbosity'] > 0.7 else ''}"
            f"{'Inject subtle humor.' if g['humor'] > 0.6 else ''}"
            f"{'Stay strictly professional.' if g['formality'] > 0.7 else ''}"
        )

    # ──────────────────────────────────────────────────────────────────
    # VERSION CONTROL
    # ──────────────────────────────────────────────────────────────────

    def _take_snapshot(self, note: str = ""):
        v = GenomeVersion(
            version=len(self._versions),
            genome=dict(self._genome),
            saved_at=datetime.now().isoformat(),
            note=note,
        )
        self._versions.append(v)
        if len(self._versions) > self.MAX_VERSIONS:
            self._versions = self._versions[-self.MAX_VERSIONS:]

    def rollback(self, version: int) -> str:
        with self._lock:
            for v in self._versions:
                if v.version == version:
                    self._genome = dict(v.genome)
                    self._save()
                    return f"Genome rolled back to version {version} ({v.saved_at})"
        return f"Version {version} not found."

    def list_versions(self) -> List[dict]:
        return [{"version": v.version, "saved_at": v.saved_at, "note": v.note}
                for v in self._versions]

    # ──────────────────────────────────────────────────────────────────
    # PRESETS / CROSSBREED
    # ──────────────────────────────────────────────────────────────────

    def apply_preset(self, preset_name: str, blend: float = 1.0) -> str:
        """Apply a named preset genome. blend=1.0 → full switch, 0.5 → 50/50."""
        preset = GENOME_PRESETS.get(preset_name.lower())
        if not preset:
            return f"Preset '{preset_name}' not found. Available: {list(GENOME_PRESETS.keys())}"
        with self._lock:
            self._take_snapshot(f"before_preset_{preset_name}")
            for trait, val in preset.items():
                if trait in self._genome:
                    self._genome[trait] = self._genome[trait] * (1 - blend) + val * blend
            self._save()
        return f"Preset '{preset_name}' applied at {blend:.0%} blend."

    def export_genome(self) -> dict:
        with self._lock:
            return {"genome": dict(self._genome), "mutations": self._mutation_count,
                    "versions": len(self._versions)}

    # ──────────────────────────────────────────────────────────────────
    # PERSISTENCE
    # ──────────────────────────────────────────────────────────────────

    def _save(self):
        try:
            data = {"genome": self._genome, "mutation_count": self._mutation_count,
                    "versions": [asdict(v) for v in self._versions[-5:]]}
            with open(self._file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug("[GENOME] Save error: %s", e)

    def _load(self):
        if not os.path.exists(self._file):
            return
        try:
            with open(self._file) as f:
                data = json.load(f)
            loaded = data.get("genome", {})
            for k, v in loaded.items():
                if k in DEFAULT_GENOME:
                    self._genome[k] = float(v)
            self._mutation_count = data.get("mutation_count", 0)
            logger.info("[GENOME] 🧬 Loaded genome (%d mutations).", self._mutation_count)
        except Exception as e:
            logger.debug("[GENOME] Load error: %s", e)

    def get_stats(self) -> dict:
        with self._lock:
            return {"genome": dict(self._genome), "total_mutations": self._mutation_count,
                    "versions_saved": len(self._versions),
                    "recent_history": self._history[-10:]}


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[DigitalGenome] = None
_lock = threading.Lock()

def get_digital_genome() -> DigitalGenome:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = DigitalGenome()
    return _instance
