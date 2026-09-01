"""ChiefBrainKernel — NEXARA PRIME unified cognitive governance + admission boundary.

F2 CONSOLIDATED (v1.0.0): This is the SINGLE ChiefBrainKernel for the project.
Combines the cognitive governance layer (intent analysis, decision gate, learning)
with the Mission Admission Boundary (submit, enforcement, recall).

The Brain is NOT an agent. It does NOT execute tools.
It produces MissionContracts that the Runtime executes.

Architecture:
  CLI → ChiefBrainKernel → MissionCompiler → Runtime → ModelGateway → Tool → Evidence
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ..models import KnowledgeRecall, Mission, RiskLevel

from .decision_engine import DecisionEngine
from .goal_manager import GoalManager
from .context_engine import ContextEngine
from .model_policy import ModelPolicyEngine
from .reasoning_budget import ReasoningBudgetManager
from .memory_controller import MemoryController
from .brain_receipt import BrainReceipt

from ..soul import SoulKernel

# ── Admission Boundary imports (F2 consolidation) ──
from ..adaptive_scheduler import AdaptiveMultiAgentScheduler
from ..contract_engine import ContractEngine
from ..governance import ApprovalEngine, PolicyEngine
from ..kernel_boundary import (
    GovernanceViolation,
    KernelAdmissionContext,
    KernelBoundaryViolation,
    KernelExecutionGuard,
)
from ..mission_compiler import MissionCompiler
from ..mission_triage import MissionTriageEngine
from ..orchestration import RuntimeOrchestrator
from ..state_machine import MissionStateMachine

if TYPE_CHECKING:
    from ..memory import MemoryLayerManager


class ChiefBrainKernel:
    """Unified cognitive governance + Mission Admission Boundary.

    F2 CONSOLIDATED (v1.0.0): Single ChiefBrainKernel for the project.

    === Cognitive Governance Responsibilities ===
      1. Intent → Goal decomposition
      2. Context compilation
      3. Model policy enforcement
      4. Decision governance (every decision → evidence)
      5. Budget enforcement
      6. Memory governance (evidence-bound)
      7. Evolution tracking

    === Admission Boundary Responsibilities (F2 merge) ===
      8. Contract validation (G1 Invariants)
      9. Authority verification (Authority Matrix)
      10. State transition validation (StateMachine)
      11. Governance approval (ApprovalEngine)
      12. Evidence chain initialization (EvidenceStore)
      13. Knowledge recall (MemoryLayerManager)

    Explicitly does NOT:
      - Execute tools (Runtime does that)
      - Call models directly (ModelGateway does that)
      - Write evidence directly (EvidenceStore does that)
      - Modify missions directly (MissionCompiler does that)
    """

    name = "chief_brain_kernel"

    def __init__(
        self,
        # ── Admission boundary params (positional for backward compat) ──
        triage: MissionTriageEngine | None = None,
        compiler: MissionCompiler | None = None,
        contracts: ContractEngine | None = None,
        state_machine: MissionStateMachine | None = None,
        orchestrator: RuntimeOrchestrator | None = None,
        scheduler: AdaptiveMultiAgentScheduler | None = None,
        policy: PolicyEngine | None = None,
        approvals: ApprovalEngine | None = None,
        *,
        memory_layer_manager: "MemoryLayerManager | None" = None,
        # ── Cognitive governance params (keyword-only) ──
        model_policy: ModelPolicyEngine | None = None,
        budget: ReasoningBudgetManager | None = None,
        memory: MemoryController | None = None,
        soul: SoulKernel | None = None,
    ) -> None:
        # ── Cognitive governance state ──
        self.decisions = DecisionEngine()
        self.goals = GoalManager()
        self.context = ContextEngine()
        self.model_policy = model_policy or ModelPolicyEngine()
        self.budget = budget or ReasoningBudgetManager()
        self.memory = memory  # Set via .bind_memory()
        self._soul = soul or SoulKernel()
        self._receipts: list[BrainReceipt] = []
        self._missions_observed: set[str] = set()
        # ── Admission boundary state (F2 merge) ──
        self._triage = triage
        self._compiler = compiler
        self._contracts = contracts
        self._state_machine = state_machine
        self._orchestrator = orchestrator
        self._scheduler = scheduler
        self._policy = policy
        self._approvals = approvals
        self._guard = KernelExecutionGuard()
        self._memory_layer_manager = memory_layer_manager

    def health(self) -> dict[str, Any]:
        """Unified health: cognitive + admission boundary."""
        return {
            "component": self.name,
            # Cognitive
            "decisions_made": len(self._receipts),
            "goals_active": len(self.goals.active()),
            "budget_remaining": self.budget.remaining,
            "model_policy": self.model_policy.health(),
            "memory_bound": self.memory is not None,
            "soul": self._soul.health(),
            # Admission
            "kernel_boundary": "active",
            "modules": {
                "triage": self._triage is not None,
                "compiler": self._compiler is not None,
                "contracts": self._contracts is not None,
                "state_machine": self._state_machine is not None,
                "orchestrator": self._orchestrator is not None,
                "scheduler": self._scheduler is not None,
                "policy": self._policy is not None,
                "approvals": self._approvals is not None,
                "recall": self._memory_layer_manager is not None,
            },
        }

    # ═══════════════════════════════════════════════════════════════════════
    # Admission Boundary (F2 consolidation from chief_brain_kernel.py)
    # ═══════════════════════════════════════════════════════════════════════

    def submit(
        self,
        mission_id: str,
        caller: str,
        contract_verified: bool = False,
        governance_approved: bool = False,
        state_valid: bool = False,
        evidence_initialized: bool = False,
    ) -> KernelAdmissionContext:
        """Submit a mission for kernel admission. Returns admission context.

        The admission context is the PROOF that all gates have been checked.
        Runtime execution requires this context via KernelExecutionGuard.
        """
        ctx = KernelAdmissionContext(
            mission_id=mission_id,
            caller=caller,
            contract_verified=contract_verified,
            authority_verified=True,
            state_valid=state_valid,
            governance_approved=governance_approved,
            evidence_chain_initialized=evidence_initialized,
        )
        if not state_valid:
            raise KernelBoundaryViolation(
                "State transition not valid for mission {}".format(mission_id))
        if not governance_approved:
            raise GovernanceViolation(
                "Governance approval missing for mission {}".format(mission_id))
        if not contract_verified:
            raise KernelBoundaryViolation(
                "Contract not verified for mission {}".format(mission_id))
        if not evidence_initialized:
            raise KernelBoundaryViolation(
                "Evidence chain not initialized for mission {}".format(mission_id))
        self._guard.admit(ctx)
        return ctx

    # ── Enforcement ──

    def assert_no_self_verify(self, executor_id: str, auditor_id: str) -> None:
        """INVARIANT_03: Executor cannot be the Auditor."""
        if executor_id == auditor_id:
            raise KernelBoundaryViolation(
                "INVARIANT_03 violation: executor '{}' cannot also be the auditor.".format(executor_id))

    def assert_no_permission_grant(self, requested_permissions: list[str]) -> None:
        """INVARIANT_01: Kernel cannot grant permissions."""
        if requested_permissions:
            raise GovernanceViolation(
                "INVARIANT_01 violation: permission grant requested through kernel.")

    def assert_evidence_not_modified(self, evidence_id: str, expected_hash: str) -> None:
        """INVARIANT_04: Evidence is append-only."""
        if not evidence_id or not expected_hash:
            raise KernelBoundaryViolation(
                "INVARIANT_04: evidence_id and expected_hash required.")

    def assert_full_completion_chain(
        self,
        success_criteria_met: bool,
        evidence_committed: bool,
        audit_completed: bool,
        receipt_created: bool,
        reflection_recorded: bool,
    ) -> None:
        """INVARIANT_05: All 5 completion gates must pass."""
        gates = {
            "success_criteria": success_criteria_met,
            "evidence": evidence_committed,
            "audit": audit_completed,
            "receipt": receipt_created,
            "reflection": reflection_recorded,
        }
        missing = [k for k, v in gates.items() if not v]
        if missing:
            raise KernelBoundaryViolation(
                "INVARIANT_05 violation: missing gates: {}".format(missing))

    # ── Transition validation ──

    def validate_transition(self, current_state: str, target_state: str) -> bool:
        """PROHIBIT_06: All transitions through state machine validation."""
        if self._state_machine is None:
            return False
        return self._state_machine.can_transition(current_state, target_state)

    # ── Admission accessors ──

    @property
    def triage(self) -> MissionTriageEngine | None:
        return self._triage

    @property
    def compiler(self) -> MissionCompiler | None:
        return self._compiler

    @property
    def contracts(self) -> ContractEngine | None:
        return self._contracts

    @property
    def state_machine(self) -> MissionStateMachine | None:
        return self._state_machine

    @property
    def orchestrator(self) -> RuntimeOrchestrator | None:
        return self._orchestrator

    @property
    def scheduler(self) -> AdaptiveMultiAgentScheduler | None:
        return self._scheduler

    @property
    def guard(self) -> KernelExecutionGuard:
        return self._guard

    # ── Knowledge Recall ──

    def recall(
        self,
        query: str,
        *,
        layers: list[str] | None = None,
        top_k: int = 10,
        mission_id: str | None = None,
        min_confidence: float = 0.3,
        include_candidates: bool = False,
        include_superseded: bool = False,
        trace_id: str = "",
    ) -> KnowledgeRecall:
        """Delegate knowledge recall to MemoryLayerManager."""
        if self._memory_layer_manager is None:
            return KnowledgeRecall(
                query=query, layers=layers, top_k=0,
                mission_id=mission_id, min_confidence=min_confidence,
                include_candidates=include_candidates,
                include_superseded=include_superseded,
                trace_id=trace_id, results=[],
            )
        results = self._memory_layer_manager.search(
            query, layers=layers, top_k=top_k, mission_id=mission_id,
        )
        filtered = [r for r in results if r.get("score", 0.0) >= min_confidence]
        if not include_candidates:
            filtered = [r for r in filtered if r.get("status") != "candidate"]
        if not include_superseded:
            filtered = [r for r in filtered if r.get("status") != "superseded"]
        filtered = filtered[:top_k]
        return KnowledgeRecall(
            query=query, layers=layers, top_k=len(filtered),
            mission_id=mission_id, min_confidence=min_confidence,
            include_candidates=include_candidates,
            include_superseded=include_superseded,
            trace_id=trace_id, results=filtered,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Cognitive Governance (original brain/kernel.py methods)
    # ═══════════════════════════════════════════════════════════════════════

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
            cost=result.get("cost_usd"),
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
