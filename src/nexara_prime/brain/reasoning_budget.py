"""ReasoningBudgetManager — token and cost tracking for brain operations.

Tracks:
  - Token usage per mission
  - Cost per model call
  - Budget remaining
  - Total run statistics
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import now_iso


# ── Cost table (USD per 1K tokens) ────────────────────────────────────────

COST_TABLE: dict[str, dict[str, float]] = {
    "deepseek-v4-flash": {"input": 0.00015, "output": 0.00060},
    "deepseek-v4-pro": {"input": 0.00200, "output": 0.00800},
    "mock": {"input": 0.0, "output": 0.0},
}


@dataclass
class BudgetUsage:
    mission_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    timestamp: str = field(default_factory=now_iso)


class ReasoningBudgetManager:
    """Tracks token usage and enforces budget constraints."""

    name = "reasoning_budget"

    def __init__(self, total_budget: float = 0.10) -> None:
        self.total_budget = total_budget
        self._used: float = 0.0
        self._total_tokens: int = 0
        self._history: list[BudgetUsage] = []

    @property
    def remaining(self) -> float:
        return max(0.0, self.total_budget - self._used)

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    def estimate(self, objective: str) -> int:
        """Estimate tokens needed for a mission based on objective length."""
        return max(100, len(objective) * 4 + 500)

    def cost_estimate(self, model: str, tokens: int) -> float:
        """Estimate cost for a model call."""
        costs = COST_TABLE.get(model, COST_TABLE["mock"])
        input_cost = (tokens * 0.75 / 1000) * costs["input"]
        output_cost = (tokens * 0.25 / 1000) * costs["output"]
        return round(input_cost + output_cost, 8)

    def record_usage(self, tokens: int, cost: float, provider: str) -> None:
        """Record actual token usage and cost."""
        self._used += cost
        self._total_tokens += tokens

    def record_call(
        self,
        mission_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> BudgetUsage:
        """Record a completed model call with cost calculation."""
        costs = COST_TABLE.get(model, COST_TABLE["mock"])
        cost = round(
            (input_tokens / 1000) * costs["input"] + (output_tokens / 1000) * costs["output"],
            8,
        )
        usage = BudgetUsage(
            mission_id=mission_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )
        self._used += cost
        self._total_tokens += input_tokens + output_tokens
        self._history.append(usage)
        return usage

    def summary(self) -> dict[str, Any]:
        return {
            "total_budget": self.total_budget,
            "used": round(self._used, 8),
            "remaining": round(self.remaining, 8),
            "total_tokens": self._total_tokens,
            "call_count": len(self._history),
        }
