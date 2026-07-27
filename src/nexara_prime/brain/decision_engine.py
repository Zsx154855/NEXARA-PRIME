"""DecisionEngine — all brain decisions produce evidence.

Every decision is a governed act: what model, why this task, why this tool, why this memory write.
Outputs DecisionOutput with evidence references for audit trail.
"""

from __future__ import annotations

from typing import Any

from ..models import new_id, now_iso


class DecisionEngine:
    """Governed decision-making for Chief Brain Kernel.

    Does NOT execute. Does NOT call models. Produces decisions that the Runtime acts on.
    """

    name = "decision_engine"

    def evaluate(
        self,
        *,
        mission_id: str,
        objective: str,
        risk_level: str,
        context: dict[str, Any],
        available_capabilities: list[str],
        budget_remaining: float,
    ) -> DecisionOutput:
        """Evaluate a mission and produce a governed decision."""
        decision_id = new_id("dec")

        # Determine action
        action = self._classify_action(risk_level, available_capabilities, budget_remaining)

        # Select model tier
        risk_num = float(risk_level[1]) / 4.0 if len(risk_level) > 1 else 0.25
        model_tier = "pro" if risk_num >= 0.5 else "flash"
        selected_model = f"deepseek-v4-{model_tier}"
        selected_provider = "deepseek"

        # Build reasoning
        reasons = [
            f"risk_level={risk_level}({risk_num:.2f})",
            f"capabilities={len(available_capabilities)}",
            f"budget_remaining={budget_remaining:.6f}",
        ]
        reasoning = f"Action={action} | Tier={model_tier} | " + " ".join(reasons)

        # Risk assessment
        if risk_num >= 0.75:
            risk_assessment = "HIGH: escalation recommended, human approval required"
        elif risk_num >= 0.5:
            risk_assessment = "MEDIUM: model routing to pro, approval required before write"
        else:
            risk_assessment = "LOW: auto-routing to flash, standard evidence required"

        return DecisionOutput(
            decision_id=decision_id,
            mission_id=mission_id,
            action=action,
            selected_model=selected_model,
            selected_provider=selected_provider,
            reasoning=reasoning,
            risk_assessment=risk_assessment,
            evidence_refs=[],
            timestamp=now_iso(),
        )

    @staticmethod
    def _classify_action(risk_level: str, capabilities: list[str], budget: float) -> str:
        if risk_level in ("R3", "R4"):
            return "escalate"
        if budget <= 0:
            return "escalate"
        if not capabilities:
            return "reject"
        if risk_level == "R2":
            return "execute" if "tool.file_write_report" in capabilities else "delegate"
        return "execute"


class DecisionOutput:
    """Governed decision with audit trail."""

    def __init__(
        self,
        decision_id: str,
        mission_id: str,
        action: str,
        selected_model: str,
        selected_provider: str,
        reasoning: str,
        risk_assessment: str,
        evidence_refs: list[str],
        timestamp: str,
    ) -> None:
        self.decision_id = decision_id
        self.mission_id = mission_id
        self.action = action
        self.selected_model = selected_model
        self.selected_provider = selected_provider
        self.reasoning = reasoning
        self.risk_assessment = risk_assessment
        self.evidence_refs = evidence_refs
        self.timestamp = timestamp
        self.estimated_tokens = 0  # populated by router later

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "mission_id": self.mission_id,
            "action": self.action,
            "selected_model": self.selected_model,
            "selected_provider": self.selected_provider,
            "reasoning": self.reasoning,
            "risk_assessment": self.risk_assessment,
            "evidence_refs": self.evidence_refs,
            "timestamp": self.timestamp,
        }
