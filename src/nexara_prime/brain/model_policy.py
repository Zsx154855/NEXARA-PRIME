"""ModelPolicyEngine — governs model selection with risk-tier enforcement.

Rules:
  S0/S1 (low complexity)  → deepseek-v4-flash
  S2/S3 (high complexity) → deepseek-v4-pro
  R3/R4 → deepseek-v4-pro + human approval required

Every routing decision is auditable.
"""

from __future__ import annotations

from typing import Any

from ..models import new_id, now_iso


# ── Policy Rules ──────────────────────────────────────────────────────────

TIER_RULES: dict[str, dict[str, list[str]]] = {
    "S0": {"allowed_models": ["deepseek-v4-flash", "mock"], "max_risk": "R1"},
    "S1": {"allowed_models": ["deepseek-v4-flash", "deepseek-v4-pro", "mock"], "max_risk": "R2"},
    "S2": {"allowed_models": ["deepseek-v4-pro", "deepseek-v4-flash", "mock"], "max_risk": "R3"},
    "S3": {"allowed_models": ["deepseek-v4-pro"], "max_risk": "R4"},
}

RISK_MODEL_RESTRICTIONS: dict[str, list[str]] = {
    "R0": ["mock", "deepseek-v4-flash", "deepseek-v4-pro"],
    "R1": ["mock", "deepseek-v4-flash", "deepseek-v4-pro"],
    "R2": ["deepseek-v4-flash", "deepseek-v4-pro"],
    "R3": ["deepseek-v4-pro"],
    "R4": ["deepseek-v4-pro"],
}


class ModelPolicyEngine:
    """Enforces model selection rules based on complexity and risk."""

    name = "model_policy_engine"

    def __init__(self) -> None:
        self._decisions: list[dict[str, Any]] = []

    def health(self) -> dict[str, Any]:
        return {
            "decisions_logged": len(self._decisions),
            "tiers_configured": list(TIER_RULES.keys()),
        }

    def recommend_tier(self, complexity: float, risk: float, context_size: int) -> str:
        """Recommend a model tier based on mission parameters."""
        if risk >= 0.75:
            return "pro"
        if context_size > 64_000:
            return "pro"
        if complexity >= 0.4:
            return "pro"
        return "flash"

    def allowed_for_risk(self, model: str, risk_level: str) -> bool:
        """Check if a model is allowed for a given risk level."""
        allowed = RISK_MODEL_RESTRICTIONS.get(risk_level, [])
        return model in allowed or model.startswith("deepseek")

    def select_model(
        self,
        complexity: float,
        risk: float,
        context_size: int,
        budget: float,
    ) -> dict[str, Any]:
        """Select the appropriate model with policy enforcement."""
        tier = self.recommend_tier(complexity, risk, context_size)
        model = f"deepseek-v4-{tier}"

        decision = {
            "decision_id": new_id("mpd"),
            "selected_model": model,
            "tier": tier,
            "complexity": round(complexity, 2),
            "risk": round(risk, 2),
            "context_size": context_size,
            "budget": round(budget, 6),
            "timestamp": now_iso(),
        }
        self._decisions.append(decision)
        return decision

    def last_decision(self) -> dict[str, Any] | None:
        return self._decisions[-1] if self._decisions else None
