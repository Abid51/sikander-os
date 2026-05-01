"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  IGRIS PARALLEL UNIVERSE TESTER                                            ║
║  "Before I act, I simulate a thousand futures."                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import math
import random
import time
import threading
import logging
from typing import List, Dict, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SimulationResult:
    action: str
    trials: int
    success_rate: float
    expected_value: float
    worst_case: float
    best_case: float
    risk_level: str          # low | medium | high | extreme
    recommendation: str
    confidence: float
    outcomes: Dict[str, float]   # outcome_label → probability
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class ParallelUniverseTester:
    """
    Monte Carlo simulation engine.

    Before Igris takes any significant action it can simulate
    N parallel outcomes and compute risk/reward ratios.

    Built-in simulation models:
    • System command risk (file delete, network change, process kill)
    • Code deployment risk (syntax errors, runtime errors)
    • Financial action risk (buy/sell decision)
    • Generic binary risk (will this work or not?)
    """

    DEFAULT_TRIALS = 1000
    MAX_TRIALS     = 10000

    def __init__(self):
        self._lock = threading.RLock()
        self._sim_history: List[SimulationResult] = []
        self._custom_models: Dict[str, Callable] = {}
        logger.info("[PARALLEL UNIVERSE] 🌀 Monte Carlo engine ready.")

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────

    def simulate(
        self,
        action: str,
        model: str = "generic",
        params: Dict[str, Any] = None,
        trials: int = DEFAULT_TRIALS,
    ) -> SimulationResult:
        """
        Run Monte Carlo simulation for an action.

        Models:
          generic    → base_success_prob  (0–1)
          system_cmd → command (str), reversible (bool)
          code_exec  → complexity (1–10), tested (bool)
          financial  → capital (float), volatility (0–1), leverage (1–10)
        """
        params = params or {}
        trials = min(trials, self.MAX_TRIALS)
        t0 = time.time()

        if model == "system_cmd":
            result = self._sim_system_cmd(action, params, trials)
        elif model == "code_exec":
            result = self._sim_code_exec(action, params, trials)
        elif model == "financial":
            result = self._sim_financial(action, params, trials)
        elif model in self._custom_models:
            result = self._custom_models[model](action, params, trials)
        else:
            result = self._sim_generic(action, params, trials)

        with self._lock:
            self._sim_history.append(result)
            if len(self._sim_history) > 500:
                self._sim_history = self._sim_history[-500:]

        elapsed = time.time() - t0
        logger.info("[PARALLEL UNIVERSE] 🎲 Simulated '%s' in %.2fs — %s (success=%.0f%%)",
                    action[:40], elapsed, result.risk_level, result.success_rate * 100)
        return result

    def should_i_do_this(self, action: str, model: str = "generic",
                         params: Dict[str, Any] = None) -> Tuple[bool, str]:
        """
        Simple yes/no answer + reason.
        Returns (proceed: bool, reasoning: str)
        """
        result = self.simulate(action, model, params, trials=500)
        proceed = result.success_rate >= 0.65 and result.risk_level not in ("extreme",)
        reason  = (
            f"After {result.trials} simulations: "
            f"Success {result.success_rate:.0%} | Risk: {result.risk_level} | "
            f"{result.recommendation}"
        )
        return proceed, reason

    def register_model(self, name: str, fn: Callable):
        """Register a custom simulation model."""
        self._custom_models[name] = fn

    # ──────────────────────────────────────────────────────────────────
    # BUILT-IN MODELS
    # ──────────────────────────────────────────────────────────────────

    def _sim_generic(self, action: str, params: dict, trials: int) -> SimulationResult:
        base_prob = float(params.get("base_success_prob", 0.7))
        base_prob = max(0.0, min(1.0, base_prob))

        successes = 0
        values: List[float] = []
        for _ in range(trials):
            noise = random.gauss(0, 0.1)
            prob  = max(0.0, min(1.0, base_prob + noise))
            outcome_val = random.uniform(0.5, 1.0) if random.random() < prob else random.uniform(-0.5, 0.0)
            values.append(outcome_val)
            if outcome_val > 0:
                successes += 1

        return self._build_result(action, trials, successes, values, params)

    def _sim_system_cmd(self, action: str, params: dict, trials: int) -> SimulationResult:
        """Simulate a system command. Irreversible commands are riskier."""
        reversible = params.get("reversible", True)
        has_backup = params.get("has_backup", False)

        # Keywords that increase risk
        dangerous_kws = ["del", "rm", "format", "rd", "kill", "shutdown", "registry"]
        risk_mult = 1.0
        for kw in dangerous_kws:
            if kw in action.lower():
                risk_mult *= 1.5

        base_prob = 0.85 / risk_mult
        if not reversible:
            base_prob *= 0.7
        if has_backup:
            base_prob = min(1.0, base_prob * 1.2)

        successes = 0
        values: List[float] = []
        for _ in range(trials):
            p = max(0.0, min(1.0, random.gauss(base_prob, 0.08)))
            val = random.uniform(0.7, 1.0) if random.random() < p else random.uniform(-1.0, -0.3)
            values.append(val)
            if val > 0:
                successes += 1

        return self._build_result(action, trials, successes, values, params)

    def _sim_code_exec(self, action: str, params: dict, trials: int) -> SimulationResult:
        """Simulate code execution risk."""
        complexity = float(params.get("complexity", 5))   # 1–10
        tested     = bool(params.get("tested", False))

        # Higher complexity = lower base success
        base_prob = max(0.3, 1.0 - (complexity / 10) * 0.5)
        if tested:
            base_prob = min(0.98, base_prob * 1.3)

        successes = 0
        values: List[float] = []
        for _ in range(trials):
            p   = max(0.0, min(1.0, random.gauss(base_prob, 0.1)))
            val = random.uniform(0.5, 1.0) if random.random() < p else random.uniform(-0.5, 0.1)
            values.append(val)
            if val > 0:
                successes += 1

        return self._build_result(action, trials, successes, values, params)

    def _sim_financial(self, action: str, params: dict, trials: int) -> SimulationResult:
        """Simulate financial decision using geometric Brownian motion."""
        capital    = float(params.get("capital", 1000.0))
        vol        = float(params.get("volatility", 0.2))    # daily volatility
        leverage   = float(params.get("leverage", 1.0))
        hold_days  = int(params.get("hold_days", 1))
        drift      = float(params.get("drift", 0.0))         # expected daily return

        profits: List[float] = []
        successes = 0
        for _ in range(trials):
            price = capital
            for _ in range(hold_days):
                daily_ret = random.gauss(drift, vol)
                price *= math.exp(daily_ret * leverage)
            pnl = (price - capital) / capital
            profits.append(pnl)
            if pnl > 0:
                successes += 1

        return self._build_result(action, trials, successes, profits, params, scale=1.0)

    # ──────────────────────────────────────────────────────────────────
    # RESULT BUILDER
    # ──────────────────────────────────────────────────────────────────

    def _build_result(
        self, action: str, trials: int,
        successes: int, values: List[float],
        params: dict, scale: float = 1.0
    ) -> SimulationResult:
        success_rate   = successes / trials
        expected_value = sum(values) / len(values)
        worst_case     = min(values)
        best_case      = max(values)

        # Risk level
        if success_rate >= 0.85 and worst_case > -0.2:
            risk_level = "low"
        elif success_rate >= 0.65 and worst_case > -0.5:
            risk_level = "medium"
        elif success_rate >= 0.45:
            risk_level = "high"
        else:
            risk_level = "extreme"

        # Confidence interval (rough 95% CI)
        sd = (sum((v - expected_value) ** 2 for v in values) / len(values)) ** 0.5
        confidence = max(0.3, 1.0 - sd)

        # Recommendation
        if risk_level == "low":
            rec = "✅ Proceed with confidence."
        elif risk_level == "medium":
            rec = "⚠️ Proceed with caution. Monitor closely."
        elif risk_level == "high":
            rec = "🚨 High risk. Consider alternatives or backup plan."
        else:
            rec = "❌ Do NOT proceed. Extremely high failure probability."

        # Outcome distribution
        bins = {"<-50%": 0, "-50% to -20%": 0, "-20% to 0%": 0,
                "0% to +20%": 0, "+20% to +50%": 0, ">+50%": 0}
        for v in values:
            if v < -0.5:   bins["<-50%"]          += 1
            elif v < -0.2: bins["-50% to -20%"]   += 1
            elif v < 0:    bins["-20% to 0%"]      += 1
            elif v < 0.2:  bins["0% to +20%"]      += 1
            elif v < 0.5:  bins["+20% to +50%"]    += 1
            else:          bins[">+50%"]            += 1
        outcomes = {k: round(v / trials, 3) for k, v in bins.items()}

        return SimulationResult(
            action=action,
            trials=trials,
            success_rate=round(success_rate, 3),
            expected_value=round(expected_value, 4),
            worst_case=round(worst_case, 4),
            best_case=round(best_case, 4),
            risk_level=risk_level,
            recommendation=rec,
            confidence=round(confidence, 3),
            outcomes=outcomes,
        )

    # ──────────────────────────────────────────────────────────────────
    # PUBLIC STATS
    # ──────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_simulations": len(self._sim_history),
                "recent_sims": [s.to_dict() for s in self._sim_history[-5:]],
                "risk_breakdown": {
                    level: sum(1 for s in self._sim_history if s.risk_level == level)
                    for level in ["low", "medium", "high", "extreme"]
                },
            }

    def get_history(self, limit: int = 20) -> List[dict]:
        with self._lock:
            return [s.to_dict() for s in self._sim_history[-limit:]]


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[ParallelUniverseTester] = None
_lock = threading.Lock()

def get_parallel_universe_tester() -> ParallelUniverseTester:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ParallelUniverseTester()
    return _instance
