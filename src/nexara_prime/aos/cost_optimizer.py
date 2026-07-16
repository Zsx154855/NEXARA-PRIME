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
    """Tracks token usage across phases and enforces budget limits."""

    def __init__(self, budget: TokenBudget | None = None) -> None:
        self.budget = budget or TokenBudget()
        self._usage: list[TokenUsage] = []
        self._model_costs: dict[str, float] = {
            "haiku": 0.25, "sonnet": 3.0, "opus": 15.0, "fable": 2.0,
            "deepseek": 0.14, "default": 3.0,
        }

    def record(self, usage: TokenUsage) -> None:
        self._usage.append(usage)

    def remaining(self) -> int:
        spent = sum(u.total for u in self._usage)
        return max(0, self.budget.maximum_budget - spent)

    def is_over_budget(self) -> bool:
        return self.remaining() == 0

    def estimate_cost(self, model: str = "default") -> float:
        rate = self._model_costs.get(model, self._model_costs["default"])
        total_tokens = sum(u.total for u in self._usage)
        return (total_tokens / 1_000_000) * rate

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
        return {
            "budget": {"total": self.budget.total, "remaining": self.remaining()},
            "over_budget": self.is_over_budget(),
            "estimated_cost_usd": round(self.estimate_cost(), 4),
            "usage_count": len(self._usage),
            "compaction_strategy": self.compaction_strategy(),
            "recommended_model": self.recommend_model("execution"),
        }
