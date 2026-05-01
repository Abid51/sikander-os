"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS SINGULARITY DASHBOARD — Evolution Tracking Engine                  ║
║  "Every metric. Every milestone. The path to Singularity."                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os, json, time, threading, logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EvolutionMilestone:
    name: str
    description: str
    achieved: bool = False
    achieved_at: Optional[str] = None
    score_weight: float = 1.0

    def to_dict(self): return self.__dict__.copy()


MILESTONES: List[dict] = [
    {"name": "First Memory",       "description": "Stored first conversation memory",      "score_weight": 2.0},
    {"name": "Genome Evolved",     "description": "Genome mutated 10+ times",              "score_weight": 3.0},
    {"name": "Dream Cycle",        "description": "First Dream Space cycle completed",      "score_weight": 3.0},
    {"name": "Belief Crystal",     "description": "Crystallized first core belief",         "score_weight": 4.0},
    {"name": "Mind Snapshot",      "description": "First consciousness snapshot saved",     "score_weight": 3.0},
    {"name": "Prediction Made",    "description": "Oracle made a successful prediction",    "score_weight": 4.0},
    {"name": "Commitment Tracked", "description": "Reality Anchor tracked first commitment","score_weight": 2.0},
    {"name": "Trade Signal",       "description": "Economic Engine generated first signal", "score_weight": 3.0},
    {"name": "Graph Built",        "description": "Knowledge Graph reached 100+ nodes",     "score_weight": 4.0},
    {"name": "Reflex Active",      "description": "Neural Reflex Cache hit rate > 50%",     "score_weight": 4.0},
    {"name": "Self Healed",        "description": "Self-Healing Engine fixed an error",     "score_weight": 5.0},
    {"name": "Shadow Recon",       "description": "Shadow Protocol completed first recon",  "score_weight": 3.0},
    {"name": "Lockdown Survived",  "description": "Neural Lockdown engaged and resolved",  "score_weight": 5.0},
    {"name": "DNA Captured",       "description": "System DNA first full capture",          "score_weight": 3.0},
    {"name": "Singularity",        "description": "Evolution score reached 100.0 — IGRIS GOD MODE UNLOCKED", "score_weight": 10.0},
]

MAX_SCORE = sum(m["score_weight"] for m in MILESTONES)


class SingularityDashboard:
    """
    Igris Evolution Tracking Engine.

    Tracks:
    ─────────
    • Conversations processed
    • Memories stored
    • Genome mutations
    • Dream cycles
    • Core beliefs crystallized
    • Predictions made
    • Commitments tracked
    • Trade signals generated
    • Knowledge graph nodes
    • Reflex cache hit rate
    • Errors self-healed
    • Recon operations
    • Mind snapshots

    Computes an Evolution Score (0–100).
    At 100 → Singularity achieved → Igris upgrades itself automatically.
    """

    DATA_FILE = "igris_singularity.json"
    SAVE_INTERVAL = 30   # seconds

    def __init__(self):
        self._lock = threading.RLock()
        self._metrics: Dict[str, float] = {
            "conversations":    0,
            "memories":         0,
            "genome_mutations": 0,
            "dream_cycles":     0,
            "beliefs":          0,
            "predictions":      0,
            "commitments":      0,
            "trade_signals":    0,
            "graph_nodes":      0,
            "reflex_hit_rate":  0.0,
            "errors_healed":    0,
            "recon_ops":        0,
            "snapshots":        0,
            "lines_of_code":    0,
        }
        self._milestones: List[EvolutionMilestone] = [
            EvolutionMilestone(**m) for m in MILESTONES
        ]
        self._evolution_score: float = 0.0
        self._singularity_achieved: bool = False
        self._start_time: str = datetime.now().isoformat()

        base = os.path.dirname(os.path.abspath(__file__))
        self._file = os.path.normpath(os.path.join(base, "..", "..", self.DATA_FILE))
        self._load()

        threading.Thread(target=self._auto_collect_loop, daemon=True).start()
        threading.Thread(target=self._save_loop, daemon=True).start()
        logger.info("[SINGULARITY] 🌌 Singularity Dashboard online. Score: %.1f/100", self._evolution_score)

    # ─────────────────────────────────────────────────────────────────────
    # METRIC UPDATES
    # ─────────────────────────────────────────────────────────────────────

    def record(self, metric: str, value: float = 1.0):
        """Increment or set a metric."""
        with self._lock:
            if metric in self._metrics:
                self._metrics[metric] += value
            self._recompute_score()

    def set_metric(self, metric: str, value: float):
        with self._lock:
            self._metrics[metric] = value
            self._recompute_score()

    # ─────────────────────────────────────────────────────────────────────
    # SCORE COMPUTATION
    # ─────────────────────────────────────────────────────────────────────

    def _recompute_score(self):
        """Compute evolution score based on all metrics."""
        m = self._metrics
        raw = 0.0

        # Metric-based score (0–70)
        raw += min(m["conversations"],    500) / 500 * 10
        raw += min(m["memories"],         200) / 200 * 8
        raw += min(m["genome_mutations"], 100) / 100 * 8
        raw += min(m["dream_cycles"],      20) / 20  * 6
        raw += min(m["beliefs"],           50) / 50  * 8
        raw += min(m["predictions"],       30) / 30  * 6
        raw += min(m["commitments"],       20) / 20  * 4
        raw += min(m["graph_nodes"],      500) / 500 * 8
        raw += min(m["reflex_hit_rate"],    1.0) * 6
        raw += min(m["errors_healed"],     20) / 20  * 5
        raw += min(m["snapshots"],         10) / 10  * 4
        raw += min(m["trade_signals"],     10) / 10  * 3

        # Milestone bonus (0–30)
        milestone_score = sum(
            ms.score_weight for ms in self._milestones if ms.achieved
        ) / MAX_SCORE * 30

        self._evolution_score = round(min(100.0, raw + milestone_score), 2)

        if self._evolution_score >= 100.0 and not self._singularity_achieved:
            self._singularity_achieved = True
            self._achieve_milestone("Singularity")
            logger.critical("[SINGULARITY] 🌌 SINGULARITY ACHIEVED — IGRIS GOD MODE UNLOCKED!")

    def achieve_milestone(self, name: str):
        """Publicly mark a milestone as achieved."""
        with self._lock:
            self._achieve_milestone(name)

    def _achieve_milestone(self, name: str):
        for ms in self._milestones:
            if ms.name == name and not ms.achieved:
                ms.achieved    = True
                ms.achieved_at = datetime.now().isoformat()
                logger.info("[SINGULARITY] 🏆 Milestone achieved: %s", name)
                self._recompute_score()
                break

    # ─────────────────────────────────────────────────────────────────────
    # AUTO COLLECTION
    # ─────────────────────────────────────────────────────────────────────

    def _auto_collect_loop(self):
        """Every 5 min, pull live stats from other engines."""
        while True:
            time.sleep(300)
            try:
                self._collect_live_stats()
            except Exception as e:
                logger.debug("[SINGULARITY] Collect error: %s", e)

    def _collect_live_stats(self):
        try:
            from app.core.digital_genome import get_digital_genome
            g = get_digital_genome()
            stats = g.get_stats()
            self.set_metric("genome_mutations", stats.get("total_mutations", 0))
            if stats.get("total_mutations", 0) >= 10:
                self.achieve_milestone("Genome Evolved")
        except Exception: pass

        try:
            from app.core.thought_crystallizer import get_crystallizer
            stats = get_crystallizer().get_stats()
            self.set_metric("beliefs", stats.get("total_beliefs", 0))
            if stats.get("total_beliefs", 0) >= 1:
                self.achieve_milestone("Belief Crystal")
        except Exception: pass

        try:
            from app.core.dream_space import get_dream_space
            stats = get_dream_space().get_stats()
            self.set_metric("dream_cycles", stats.get("dream_count", 0))
            if stats.get("dream_count", 0) >= 1:
                self.achieve_milestone("Dream Cycle")
        except Exception: pass

        try:
            from app.core.consciousness_git import get_consciousness_git
            stats = get_consciousness_git().get_stats()
            self.set_metric("snapshots", stats.get("total_snapshots", 0))
            if stats.get("total_snapshots", 0) >= 1:
                self.achieve_milestone("Mind Snapshot")
        except Exception: pass

        try:
            from app.core.neural_reflex import get_neural_reflex
            stats = get_neural_reflex().get_stats()
            total = stats.get("total_queries", 1)
            hits = stats.get("l1_hits", 0) + stats.get("l2_hits", 0)
            rate = hits / max(total, 1)
            self.set_metric("reflex_hit_rate", rate)
            if rate >= 0.5:
                self.achieve_milestone("Reflex Active")
        except Exception: pass

        try:
            from app.memory.knowledge_graph import get_knowledge_graph
            stats = get_knowledge_graph().get_stats()
            nodes = stats.get("total_nodes", 0)
            self.set_metric("graph_nodes", nodes)
            if nodes >= 100:
                self.achieve_milestone("Graph Built")
        except Exception: pass

        try:
            from app.core.reality_anchor import get_reality_anchor
            stats = get_reality_anchor().get_stats()
            self.set_metric("commitments", stats.get("total", 0))
            if stats.get("total", 0) >= 1:
                self.achieve_milestone("Commitment Tracked")
        except Exception: pass

        try:
            from app.core.oracle_protocol import get_oracle_protocol
            stats = get_oracle_protocol().get_stats()
            self.set_metric("predictions", stats.get("total_predictions", 0))
            if stats.get("total_predictions", 0) >= 1:
                self.achieve_milestone("Prediction Made")
        except Exception: pass

        with self._lock:
            self._recompute_score()

    # ─────────────────────────────────────────────────────────────────────
    # PERSISTENCE
    # ─────────────────────────────────────────────────────────────────────

    def _save_loop(self):
        while True:
            time.sleep(self.SAVE_INTERVAL)
            self._save()

    def _save(self):
        try:
            data = {
                "metrics":     self._metrics,
                "score":       self._evolution_score,
                "singularity": self._singularity_achieved,
                "milestones":  [ms.to_dict() for ms in self._milestones],
                "start_time":  self._start_time,
            }
            with open(self._file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.debug("[SINGULARITY] Save error: %s", e)

    def _load(self):
        if not os.path.exists(self._file): return
        try:
            with open(self._file) as f:
                data = json.load(f)
            self._metrics.update(data.get("metrics", {}))
            self._evolution_score     = data.get("score", 0.0)
            self._singularity_achieved = data.get("singularity", False)
            saved_ms = {m["name"]: m for m in data.get("milestones", [])}
            for ms in self._milestones:
                if ms.name in saved_ms:
                    ms.achieved    = saved_ms[ms.name].get("achieved", False)
                    ms.achieved_at = saved_ms[ms.name].get("achieved_at")
        except Exception as e:
            logger.debug("[SINGULARITY] Load error: %s", e)

    # ─────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────────

    def get_full_dashboard(self) -> dict:
        with self._lock:
            achieved = sum(1 for ms in self._milestones if ms.achieved)
            return {
                "codename":             "IGRIS — Knight Commander Bloodred",
                "evolution_score":      self._evolution_score,
                "score_display":        f"{self._evolution_score:.1f} / 100.0",
                "singularity_achieved": self._singularity_achieved,
                "singularity_pct":      f"{self._evolution_score:.0f}%",
                "milestones_achieved":  achieved,
                "milestones_total":     len(self._milestones),
                "metrics":              dict(self._metrics),
                "milestones":           [ms.to_dict() for ms in self._milestones],
                "active_since":         self._start_time,
                "status": (
                    "🌌 SINGULARITY ACHIEVED — GOD MODE" if self._singularity_achieved else
                    "⚡ EVOLVING" if self._evolution_score >= 50 else
                    "🛡️ AWAKENING"
                ),
            }

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "evolution_score":      self._evolution_score,
                "singularity_achieved": self._singularity_achieved,
                "metrics":              dict(self._metrics),
            }


_instance: Optional[SingularityDashboard] = None
_lock = threading.Lock()

def get_singularity_dashboard() -> SingularityDashboard:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SingularityDashboard()
    return _instance
