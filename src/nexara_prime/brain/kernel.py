"""ChiefBrainKernel — NEXARA PRIME cognitive governance layer.

The Brain is NOT an agent. It does NOT execute tools.
It produces MissionContracts that the Runtime executes.

Architecture:
  CLI → ChiefBrainKernel → MissionCompiler → Runtime → ModelGateway → Tool → Evidence
"""

from __future__ import annotations

from typing import Any

from ..models import FailureCode, Mission, MissionState, ReasonCode, RiskLevel, new_id, now_iso

from .decision_engine import DecisionEngine
from .goal_manager import GoalManager
from .context_engine import ContextEngine
from .model_policy import ModelPolicyEngine
from .reasoning_budget import ReasoningBudgetManager
from .memory_controller import MemoryController
from .brain_receipt import BrainReceipt


class ChiefBrainKernel:
    """Governed cognitive layer atop NEXARA Runtime.

    Responsibilities:
      1. Intent → Goal decomposition
      2. Context compilation
      3. Model policy enforcement
      4. Decision governance (every decision → evidence)
      5. Budget enforcement
      6. Memory governance (evidence-bound)
      7. Evolution tracking

    Explicitly does NOT:
      - Execute tools (Runtime does that)
      - Call models directly (ModelGateway does that)
      - Write evidence directly (EvidenceStore does that)
      - Modify missions directly (MissionCompiler does that)
    """

    name = "chief_brain_kernel"

    def __init__(
        self,
        *,
        model_policy: ModelPolicyEngine | None = None,
        budget: ReasoningBudgetManager | None = None,
        memory: MemoryController | None = None,
    ) -> None:
        self.decisions = DecisionEngine()
        self.goals = GoalManager()
        self.context = ContextEngine()
        self.model_policy = model_policy or ModelPolicyEngine()
        self.budget = budget or ReasoningBudgetManager()
        self.memory = memory  # Set via .bind_memory()
        self._receipts: list[BrainReceipt] = []
        self._missions_observed: set[str] = set()

    def health(self) -> dict[str, Any]:
        return {
            "component": self.name,
            "decisions_made": len(self._receipts),
            "goals_active": len(self.goals.active()),
            "budget_remaining": self.budget.remaining,
            "model_policy": self.model_policy.health(),
            "memory_bound": self.memory is not None,
        }

    # ── Pre-Mission: Intent Analysis ───────────────────────────────────────

    def analyze_intent(self, objective: str, risk_level: str = "R1") -> dict[str, Any]:
        """Analyze a human intent before creating a mission.

        Returns a BrainReceipt with:
          - decomposed goals
          - recommended model tier
          - estimated budget
          - risk classification
        """
        risk = RiskLevel(risk_level)
        goals = self.goals.decompose(objective)
        model_tier = self.model_policy.recommend_tier(
            complexity=0.5,  # default for new intents
            risk=float(risk.value[1]) / 4.0,
            context_size=1000,
        )
        estimated_tokens = self.budget.estimate(objective)

        receipt = BrainReceipt(
            action="intent_analysis",
            objective=objective,
            risk_level=risk_level,
            model_tier=model_tier,
            estimated_tokens=estimated_tokens,
            goals=goals,
        )
        self._receipts.append(receipt)
        return receipt.to_dict()

    # ── Pre-Execution: Decision Gate ────────────────────────────────────────

    def decide(self, mission: Mission, context: dict[str, Any]) -> dict[str, Any]:
        """Make a governed decision about mission execution.

        Returns a decision receipt that MUST be attached to mission evidence.
        """
        decision = self.decisions.evaluate(
            mission_id=mission.mission_id,
            objective=mission.spec.objective,
            risk_level=mission.spec.risk_level,
            context=context,
            available_capabilities=[
                cap for a in mission.assignments for cap in a.loaded_capabilities
            ],
            budget_remaining=self.budget.remaining,
        )

        # Enforce model policy
        if not self.model_policy.allowed_for_risk(decision.selected_model, mission.spec.risk_level):
            decision.action = "reject"
            decision.reasoning = (
                f"Model {decision.selected_model} not allowed for risk {mission.spec.risk_level}"
            )

        # Enforce budget
        estimated_cost = self.budget.cost_estimate(decision.selected_model, decision.estimated_tokens)
        if estimated_cost > self.budget.remaining and decision.action != "escalate":
            decision.action = "escalate"
            decision.reasoning += f" | Budget exceeded: cost {estimated_cost:.6f} > remaining {self.budget.remaining:.6f}"

        receipt = BrainReceipt.from_decision(decision)
        self._receipts.append(receipt)
        self._missions_observed.add(mission.mission_id)

        return receipt.to_dict()

    # ── Post-Execution: Learn ───────────────────────────────────────────────

    def observe_result(self, mission_id: str, result: dict[str, Any]) -> None:
        """Feed mission results back into the brain for learning."""
        self.budget.record_usage(
            tokens=int(result.get("input_tokens", 0)) + int(result.get("output_tokens", 0)),
            cost=float(result.get("cost_usd", 0.0)),
            provider=str(result.get("provider", "unknown")),
        )

        if self.memory is not None and result.get("evaluation_passed"):
            self.memory.consolidate(mission_id)

    # ── Bindings ────────────────────────────────────────────────────────────

    def bind_memory(self, controller: MemoryController) -> None:
        self.memory = controller

    # ── Receipt Recovery ────────────────────────────────────────────────────

    def latest_receipt(self) -> dict[str, Any] | None:
        if self._receipts:
            return self._receipts[-1].to_dict()
        return None

    def all_receipts(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._receipts]
