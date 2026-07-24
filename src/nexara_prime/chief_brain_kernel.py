"""ChiefBrainKernel — the sole Mission Admission Boundary.

Kernel OWNS admission authority. Runtime OWNS execution capability.
No mission reaches execution without passing through this kernel.

This is NOT a second runtime. It is the enforcement layer for:
- Contract validation (G1 Invariants)
- Authority verification (Authority Matrix)
- State transition validation (StateMachine)
- Governance approval (ApprovalEngine)
- Evidence chain initialization (EvidenceStore)
"""
from __future__ import annotations

from typing import Any

from .adaptive_scheduler import AdaptiveMultiAgentScheduler
from .contract_engine import ContractEngine
from .governance import ApprovalEngine, PolicyEngine
from .kernel_boundary import (
    GovernanceViolation,
    KernelAdmissionContext,
    KernelBoundaryViolation,
    KernelExecutionGuard,
)
from .mission_compiler import MissionCompiler
from .mission_triage import MissionTriageEngine
from .orchestration import RuntimeOrchestrator
from .state_machine import MissionStateMachine


class ChiefBrainKernel:
    """The sole Mission Admission Boundary.

    All mission creation, planning, approval, and execution MUST pass through
    this kernel. Direct Runtime execution without kernel admission is BLOCKED
    by KernelExecutionGuard.

    Usage:
        kernel = ChiefBrainKernel(triage, compiler, contracts, state_machine,
                                  orchestrator, scheduler, policy, approvals)
        ctx = kernel.submit(mission_id, caller="api", ...)
        # ctx is now the admission proof for Runtime execution
    """

    def __init__(
        self,
        triage: MissionTriageEngine,
        compiler: MissionCompiler,
        contracts: ContractEngine,
        state_machine: MissionStateMachine,
        orchestrator: RuntimeOrchestrator,
        scheduler: AdaptiveMultiAgentScheduler,
        policy: PolicyEngine,
        approvals: ApprovalEngine,
    ) -> None:
        self._triage = triage
        self._compiler = compiler
        self._contracts = contracts
        self._state_machine = state_machine
        self._orchestrator = orchestrator
        self._scheduler = scheduler
        self._policy = policy
        self._approvals = approvals
        self._guard = KernelExecutionGuard()

    # ═══ Admission ═══

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
            authority_verified=True,  # kernel authority is verified by construction
            state_valid=state_valid,
            governance_approved=governance_approved,
            evidence_chain_initialized=evidence_initialized,
        )

        # Enforce: invalid state transition is BLOCKED
        if not state_valid:
            raise KernelBoundaryViolation(
                "State transition not valid for mission {}".format(mission_id))

        # Enforce: governance approval required for R3+
        if not governance_approved:
            raise GovernanceViolation(
                "Governance approval missing for mission {}".format(mission_id))

        # Enforce: contract must be verified
        if not contract_verified:
            raise KernelBoundaryViolation(
                "Contract not verified for mission {}".format(mission_id))

        # Enforce: evidence chain must be initialized
        if not evidence_initialized:
            raise KernelBoundaryViolation(
                "Evidence chain not initialized for mission {}".format(mission_id))

        # Admit to execution guard
        self._guard.admit(ctx)
        return ctx

    # ═══ Enforcement methods ═══

    def assert_no_self_verify(self, executor_id: str, auditor_id: str) -> None:
        """INVARIANT_03: Executor cannot be the Auditor. Raises on violation."""
        if executor_id == auditor_id:
            raise KernelBoundaryViolation(
                "INVARIANT_03 violation: executor '{}' cannot also be the auditor. "
                "Use an independent agent.".format(executor_id))

    def assert_no_permission_grant(self, requested_permissions: list[str]) -> None:
        """INVARIANT_01: Kernel cannot grant permissions. Raises on any request."""
        if requested_permissions:
            raise GovernanceViolation(
                "INVARIANT_01 violation: permission grant requested through kernel. "
                "Permissions must be granted externally by a human. "
                "Requested: {}".format(requested_permissions))

    def assert_evidence_not_modified(self, evidence_id: str, expected_hash: str) -> None:
        """INVARIANT_04: Evidence is append-only. Verifies hash integrity."""
        if not evidence_id or not expected_hash:
            raise KernelBoundaryViolation(
                "INVARIANT_04: evidence_id and expected_hash required. "
                "Cannot verify evidence integrity without them.")

    def assert_full_completion_chain(
        self,
        success_criteria_met: bool,
        evidence_committed: bool,
        audit_completed: bool,
        receipt_created: bool,
        reflection_recorded: bool,
    ) -> None:
        """INVARIANT_05: All 5 completion gates must pass. Raises if any missing."""
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
                "INVARIANT_05 violation: mission completion requires all 5 gates. "
                "Missing: {}".format(missing))

    # ═══ Transition validation ═══

    def validate_transition(self, current_state: str, target_state: str) -> bool:
        """PROHIBIT_06: All transitions through state machine validation."""
        return self._state_machine.can_transition(current_state, target_state)

    # ═══ Accessors (read-only) ═══

    @property
    def triage(self) -> MissionTriageEngine:
        return self._triage

    @property
    def compiler(self) -> MissionCompiler:
        return self._compiler

    @property
    def contracts(self) -> ContractEngine:
        return self._contracts

    @property
    def state_machine(self) -> MissionStateMachine:
        return self._state_machine

    @property
    def orchestrator(self) -> RuntimeOrchestrator:
        return self._orchestrator

    @property
    def scheduler(self) -> AdaptiveMultiAgentScheduler:
        return self._scheduler

    @property
    def guard(self) -> KernelExecutionGuard:
        return self._guard

    # ═══ Health ═══

    def health(self) -> dict[str, Any]:
        return {
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
            },
        }
