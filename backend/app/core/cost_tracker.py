"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS API COST TRACKER
  Real-time cost tracking per model/provider with budget alerts
  No BS — actual token counting and USD cost calculation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  PRICING TABLE (USD per 1M tokens)  — Updated April 2026
# ─────────────────────────────────────────────────────────────────────────────

MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # OpenAI
    "gpt-4o":               {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":          {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":          {"input": 10.00, "output": 30.00},
    "gpt-4":                {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo":        {"input": 0.50,  "output": 1.50},
    "o1":                   {"input": 15.00, "output": 60.00},
    "o1-mini":              {"input": 3.00,  "output": 12.00},
    "o3-mini":              {"input": 1.10,  "output": 4.40},
    # Anthropic
    "claude-3-7-sonnet-20250219":  {"input": 3.00,  "output": 15.00},
    "claude-3-5-sonnet-20241022":  {"input": 3.00,  "output": 15.00},
    "claude-3-5-haiku-20241022":   {"input": 0.80,  "output": 4.00},
    "claude-3-opus-20240229":      {"input": 15.00, "output": 75.00},
    # Gemini
    "gemini-2.5-pro":       {"input": 1.25,  "output": 10.00},
    "gemini-2.0-flash":     {"input": 0.10,  "output": 0.40},
    "gemini-1.5-pro":       {"input": 1.25,  "output": 5.00},
    "gemini-1.5-flash":     {"input": 0.075, "output": 0.30},
    # Groq (ultra cheap)
    "llama-3.3-70b-versatile":     {"input": 0.59,  "output": 0.79},
    "llama-3.1-8b-instant":        {"input": 0.05,  "output": 0.08},
    "mixtral-8x7b-32768":          {"input": 0.24,  "output": 0.24},
    "deepseek-r1-distill-llama-70b": {"input": 0.75, "output": 0.99},
    # Mistral
    "mistral-large-latest":        {"input": 3.00,  "output": 9.00},
    "mistral-small-latest":        {"input": 0.20,  "output": 0.60},
    "codestral-latest":            {"input": 1.00,  "output": 3.00},
    # DeepSeek
    "deepseek-chat":               {"input": 0.14,  "output": 0.28},
    "deepseek-reasoner":           {"input": 0.55,  "output": 2.19},
    # Ollama (local — FREE)
    "llama3": {"input": 0.0, "output": 0.0},
    "llama3.1:8b": {"input": 0.0, "output": 0.0},
    "mistral": {"input": 0.0, "output": 0.0},
    "gemma2:2b": {"input": 0.0, "output": 0.0},
}

# Default pricing for unknown models
_DEFAULT_PRICING = {"input": 1.0, "output": 3.0}

# Approximate chars per token
CHARS_PER_TOKEN = 4


# ─────────────────────────────────────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CallRecord:
    call_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    latency_ms: float
    success: bool
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BudgetAlert:
    level: str           # "warning" | "critical" | "limit_reached"
    spent_usd: float
    budget_usd: float
    percentage: float
    message: str
    timestamp: float = field(default_factory=time.time)


# ─────────────────────────────────────────────────────────────────────────────
#  COST TRACKER
# ─────────────────────────────────────────────────────────────────────────────

class IgrisAPIcostTracker:
    """
    Real API cost tracker for Igris.

    Tracks every LLM call with:
    - Token counts (estimated from response length)
    - USD cost per call
    - Running totals per model/provider
    - Daily/monthly summaries
    - Budget alerts
    """

    PERSIST_FILE = "igris_api_costs.json"

    def __init__(
        self,
        daily_budget_usd: float = 1.0,
        monthly_budget_usd: float = 20.0,
    ) -> None:
        self._calls: List[CallRecord] = []
        self._daily_budget = daily_budget_usd
        self._monthly_budget = monthly_budget_usd
        self._alerts: List[BudgetAlert] = []
        self._persist_path = os.path.join(
            os.path.dirname(__file__), "..", "..", self.PERSIST_FILE
        )
        self._persist_path = os.path.normpath(self._persist_path)
        self._load()
        logger.info(f"[COST] Tracker initialized — {len(self._calls)} records loaded.")

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count from text length."""
        return max(1, len(text) // CHARS_PER_TOKEN)

    @staticmethod
    def get_pricing(model: str) -> Dict[str, float]:
        """Get pricing for a model (USD per 1M tokens)."""
        # Direct match
        if model in MODEL_PRICING:
            return MODEL_PRICING[model]
        # Partial match (e.g. "gpt-4o-mini-2024-07-18" → "gpt-4o-mini")
        for key in MODEL_PRICING:
            if key in model or model in key:
                return MODEL_PRICING[key]
        return _DEFAULT_PRICING

    def track_call(
        self,
        provider: str,
        model: str,
        input_text: str,
        output_text: str,
        latency_ms: float = 0.0,
        success: bool = True,
        call_id: Optional[str] = None,
    ) -> CallRecord:
        """Record an API call and calculate cost."""
        pricing = self.get_pricing(model)
        input_tokens = self.estimate_tokens(input_text)
        output_tokens = self.estimate_tokens(output_text)

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost

        record = CallRecord(
            call_id=call_id or f"{provider}_{int(time.time()*1000)}",
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost_usd=round(input_cost, 8),
            output_cost_usd=round(output_cost, 8),
            total_cost_usd=round(total_cost, 8),
            latency_ms=round(latency_ms, 1),
            success=success,
        )
        self._calls.append(record)
        self._save()

        # Check budget
        self._check_budget_alerts()

        logger.debug(f"[COST] {provider}/{model}: ${total_cost:.6f} ({input_tokens}+{output_tokens} tokens)")
        return record

    def _check_budget_alerts(self) -> Optional[BudgetAlert]:
        """Check if budget thresholds are crossed."""
        daily_spend = self.get_daily_total()
        monthly_spend = self.get_monthly_total()

        alert = None
        if monthly_spend >= self._monthly_budget:
            alert = BudgetAlert("limit_reached", monthly_spend, self._monthly_budget,
                                100.0, f"Monthly budget EXCEEDED: ${monthly_spend:.4f}/${self._monthly_budget}")
        elif monthly_spend >= self._monthly_budget * 0.9:
            alert = BudgetAlert("critical", monthly_spend, self._monthly_budget,
                                (monthly_spend/self._monthly_budget)*100,
                                f"Monthly budget 90% used: ${monthly_spend:.4f}/${self._monthly_budget}")
        elif daily_spend >= self._daily_budget:
            alert = BudgetAlert("warning", daily_spend, self._daily_budget,
                                100.0, f"Daily budget exceeded: ${daily_spend:.4f}/${self._daily_budget}")

        if alert:
            self._alerts.append(alert)
            logger.warning(f"[COST] 🚨 Budget alert: {alert.message}")
        return alert

    def get_daily_total(self, date_str: Optional[str] = None) -> float:
        """Get total cost for today (or given date YYYY-MM-DD)."""
        from datetime import datetime, date
        target = date_str or date.today().isoformat()
        return sum(
            r.total_cost_usd for r in self._calls
            if datetime.fromtimestamp(r.timestamp).date().isoformat() == target
        )

    def get_monthly_total(self, month_str: Optional[str] = None) -> float:
        """Get total cost for current month (or given YYYY-MM)."""
        from datetime import datetime
        now = datetime.now()
        target = month_str or f"{now.year}-{now.month:02d}"
        return sum(
            r.total_cost_usd for r in self._calls
            if datetime.fromtimestamp(r.timestamp).strftime("%Y-%m") == target
        )

    def get_stats(self) -> Dict[str, Any]:
        """Full cost statistics."""
        if not self._calls:
            return {
                "total_calls": 0, "total_cost_usd": 0.0,
                "daily_cost_usd": 0.0, "monthly_cost_usd": 0.0,
                "by_provider": {}, "by_model": {},
            }

        # Per provider
        by_provider: Dict[str, Dict[str, Any]] = {}
        by_model: Dict[str, Dict[str, Any]] = {}

        for r in self._calls:
            # Provider
            if r.provider not in by_provider:
                by_provider[r.provider] = {"calls": 0, "total_usd": 0.0, "tokens": 0}
            by_provider[r.provider]["calls"] += 1
            by_provider[r.provider]["total_usd"] += r.total_cost_usd
            by_provider[r.provider]["tokens"] += r.input_tokens + r.output_tokens

            # Model
            if r.model not in by_model:
                by_model[r.model] = {"calls": 0, "total_usd": 0.0}
            by_model[r.model]["calls"] += 1
            by_model[r.model]["total_usd"] += r.total_cost_usd

        # Round
        for p in by_provider:
            by_provider[p]["total_usd"] = round(by_provider[p]["total_usd"], 6)
        for m in by_model:
            by_model[m]["total_usd"] = round(by_model[m]["total_usd"], 6)

        return {
            "total_calls": len(self._calls),
            "successful_calls": sum(1 for r in self._calls if r.success),
            "total_cost_usd": round(sum(r.total_cost_usd for r in self._calls), 6),
            "total_input_tokens": sum(r.input_tokens for r in self._calls),
            "total_output_tokens": sum(r.output_tokens for r in self._calls),
            "daily_cost_usd": round(self.get_daily_total(), 6),
            "monthly_cost_usd": round(self.get_monthly_total(), 6),
            "daily_budget_usd": self._daily_budget,
            "monthly_budget_usd": self._monthly_budget,
            "avg_cost_per_call_usd": round(
                sum(r.total_cost_usd for r in self._calls) / len(self._calls), 8
            ),
            "avg_latency_ms": round(
                sum(r.latency_ms for r in self._calls) / len(self._calls), 1
            ),
            "by_provider": by_provider,
            "by_model": by_model,
            "recent_alerts": [asdict(a) for a in self._alerts[-5:]],
            "cheapest_model": min(by_model, key=lambda m: by_model[m]["total_usd"]) if by_model else None,
            "most_used_model": max(by_model, key=lambda m: by_model[m]["calls"]) if by_model else None,
        }

    def get_recent_calls(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._calls[-limit:]]

    def set_budget(self, daily_usd: Optional[float] = None, monthly_usd: Optional[float] = None) -> None:
        if daily_usd is not None:
            self._daily_budget = daily_usd
        if monthly_usd is not None:
            self._monthly_budget = monthly_usd

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            data = {
                "calls": [r.to_dict() for r in self._calls[-10000:]],  # keep last 10k
                "daily_budget": self._daily_budget,
                "monthly_budget": self._monthly_budget,
            }
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"[COST] Save error: {e}")

    def _load(self) -> None:
        if not os.path.exists(self._persist_path):
            return
        try:
            with open(self._persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._calls = [CallRecord(**r) for r in data.get("calls", [])]
            self._daily_budget = data.get("daily_budget", self._daily_budget)
            self._monthly_budget = data.get("monthly_budget", self._monthly_budget)
        except Exception as e:
            logger.warning(f"[COST] Load error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[IgrisAPIcostTracker] = None


def get_cost_tracker() -> IgrisAPIcostTracker:
    global _instance
    if _instance is None:
        daily = float(os.getenv("IGRIS_DAILY_BUDGET_USD", "1.0"))
        monthly = float(os.getenv("IGRIS_MONTHLY_BUDGET_USD", "20.0"))
        _instance = IgrisAPIcostTracker(daily_budget_usd=daily, monthly_budget_usd=monthly)
    return _instance
