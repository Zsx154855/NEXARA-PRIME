"""Token cost optimizer — tracks usage, enforces budgets, routes models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TokenBudget:
    planning_budget: int = 50000
    execution_budget: int = 200000
    review_budget: int = 50000
    recovery_budget: int = 30000
    maximum_budget: int = 350000

    @property
    def total(self) -> int:
        return self.planning_budget + self.execution_budget + self.review_budget + self.recovery_budget


@dataclass
class TokenUsage:
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    mission_id: str = ""
    phase: str = ""

    @property
    def total(self) -> int:
        return self.tokens_in + self.tokens_out


class CostOptimizer:
    """Tracks token usage across phases and enforces budget limits.

    Cost estimation uses per-model rates — each TokenUsage is costed at
    its own model/provider rate, supporting mixed-model missions.
    """

    # Per-model cost in USD per 1M tokens (input / output if different,
    # otherwise single blended rate)
    _MODEL_RATES: dict[str, dict[str, float]] = {
        # Anthropic models (per 1M tokens, input/output)
        "haiku":   {"input": 0.25, "output": 1.25},
        "sonnet":  {"input": 3.00, "output": 15.00},
        "opus":    {"input": 15.00, "output": 75.00},
        "fable":   {"input": 2.00, "output": 10.00},
        # DeepSeek models
        "deepseek":         {"input": 0.14, "output": 0.28},
        "deepseek-v4":      {"input": 0.14, "output": 0.28},
        "deepseek-v4-pro":  {"input": 0.14, "output": 0.28},
        "deepseek-v4-flash":{"input": 0.14, "output": 0.28},
        # OpenAI models
        "gpt-4o":    {"input": 2.50, "output": 10.00},
        "gpt-4o-mini":{"input": 0.15, "output": 0.60},
        "o3":        {"input": 10.00, "output": 40.00},
        # Fallback
        "default": {"input": 3.00, "output": 15.00},
    }

    def __init__(self, budget: TokenBudget | None = None) -> None:
        self.budget = budget or TokenBudget()
        self._usage: list[TokenUsage] = []

    def record(self, usage: TokenUsage) -> None:
        self._usage.append(usage)

    def remaining(self) -> int:
        spent = sum(u.total for u in self._usage)
        return max(0, self.budget.maximum_budget - spent)

    def is_over_budget(self) -> bool:
        return self.remaining() == 0

    def _get_rate(self, model: str) -> dict[str, float]:
        """Find rate for a model by prefix match, falling back to 'default'."""
        model_lower = model.lower()
        # Try exact match first
        if model_lower in self._MODEL_RATES:
            return self._MODEL_RATES[model_lower]
        # Try prefix match (e.g. "sonnet-4.6" → "sonnet")
        for key in sorted(self._MODEL_RATES.keys(), key=len, reverse=True):
            if key != "default" and model_lower.startswith(key):
                return self._MODEL_RATES[key]
        return self._MODEL_RATES["default"]

    def estimate_cost(self, model: str = "default") -> float:
        """Estimate cost for a single model (backward-compatible).

        For accurate mixed-model cost, use estimate_cost_per_usage().
        """
        rates = self._get_rate(model)
        total_tokens = sum(u.total for u in self._usage)
        avg_rate = (rates["input"] + rates["output"]) / 2
        return (total_tokens / 1_000_000) * avg_rate

    def estimate_cost_per_usage(self) -> dict[str, Any]:
        """Estimate cost by summing each TokenUsage at its own model rate.

        Returns detailed breakdown suitable for evidence records.
        """
        per_model: dict[str, dict[str, float]] = {}
        total_cost = 0.0

        for usage in self._usage:
            model_key = usage.model or "default"
            rates = self._get_rate(model_key)
            input_cost = (usage.tokens_in / 1_000_000) * rates["input"]
            output_cost = (usage.tokens_out / 1_000_000) * rates["output"]
            usage_cost = input_cost + output_cost
            total_cost += usage_cost

            if model_key not in per_model:
                per_model[model_key] = {
                    "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
                    "input_rate": rates["input"], "output_rate": rates["output"],
                }
            per_model[model_key]["tokens_in"] += usage.tokens_in
            per_model[model_key]["tokens_out"] += usage.tokens_out
            per_model[model_key]["cost_usd"] += usage_cost

        return {
            "total_cost_usd": round(total_cost, 6),
            "per_model": {
                m: {**v, "cost_usd": round(v["cost_usd"], 6)}
                for m, v in per_model.items()
            },
            "usage_count": len(self._usage),
        }

    def recommend_model(self, phase: str) -> str:
        """Route to cheaper model for low-complexity phases."""
        budget_pct = self.remaining() / max(1, self.budget.maximum_budget)
        if phase in ("planning", "review", "recovery"):
            if budget_pct < 0.3:
                return "haiku"
            return "sonnet"
        if phase == "execution":
            if budget_pct < 0.2:
                return "haiku"
            elif budget_pct < 0.5:
                return "sonnet"
            return "opus"
        return "sonnet"

    def compaction_strategy(self) -> str:
        budget_pct = self.remaining() / max(1, self.budget.maximum_budget)
        if budget_pct < 0.1:
            return "aggressive"
        elif budget_pct < 0.3:
            return "moderate"
        return "none"

    def to_evidence(self) -> dict[str, Any]:
        cost_detail = self.estimate_cost_per_usage()
        return {
            "budget": {"total": self.budget.total, "remaining": self.remaining()},
            "over_budget": self.is_over_budget(),
            "estimated_cost_usd": round(cost_detail["total_cost_usd"], 4),
            "cost_detail": cost_detail,
            "usage_count": len(self._usage),
            "compaction_strategy": self.compaction_strategy(),
            "recommended_model": self.recommend_model("execution"),
        }
