"""BrainReceipt — immutable decision evidence.

Every brain decision produces a receipt with:
  - What was decided
  - Why (reasoning chain)
  - Model used
  - Risk assessment
  - Evidence references

Receipts are append-only and serve as the brain's audit trail.
"""

from __future__ import annotations

from typing import Any

from ..models import new_id, now_iso


class BrainReceipt:
    """Immutable record of a brain decision.

    Generated for every: intent analysis, model selection, routing decision,
    memory write, goal change, and evolution observation.
    """

    def __init__(
        self,
        action: str,
        objective: str = "",
        risk_level: str = "R1",
        model_tier: str = "",
        estimated_tokens: int = 0,
        goals: list[dict[str, Any]] | None = None,
        decision: Any = None,
    ) -> None:
        self.receipt_id = new_id("br")
        self.action = action
        self.objective = objective
        self.risk_level = risk_level
        self.model_tier = model_tier
        self.estimated_tokens = estimated_tokens
        self.goals = goals or []
        self.decision = decision
        self.timestamp = now_iso()

    @classmethod
    def from_decision(cls, decision: Any) -> "BrainReceipt":
        """Create a receipt from a DecisionOutput."""
        return cls(
            action=decision.action,
            objective=getattr(decision, "mission_id", ""),
            risk_level=getattr(decision, "risk_assessment", "R1"),
            model_tier=getattr(decision, "selected_model", ""),
            decision=decision,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "receipt_id": self.receipt_id,
            "action": self.action,
            "objective": self.objective,
            "risk_level": self.risk_level,
            "model_tier": self.model_tier,
            "estimated_tokens": self.estimated_tokens,
            "timestamp": self.timestamp,
        }
        if self.goals:
            result["goals"] = self.goals
        if self.decision:
            if hasattr(self.decision, "to_dict"):
                result["decision"] = self.decision.to_dict()
            elif isinstance(self.decision, dict):
                result["decision"] = self.decision
            else:
                result["decision"] = str(self.decision)
        return result
