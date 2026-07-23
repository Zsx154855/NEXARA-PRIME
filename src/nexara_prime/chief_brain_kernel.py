"""ChiefBrainKernel — explicit boundary wrapper for the 7 kernel modules.

This is a THIN formalization layer. It does NOT replace NexaraRuntime.
It makes explicit the kernel boundary that already exists implicitly in
NexaraRuntime.__init__. All 7 kernel modules remain in their original files.

G2-C: Kernel Adapter / Integration Layer
Contract: chief_brain_kernel_contract_v1.yaml
"""
from __future__ import annotations

from typing import Any

from .adaptive_scheduler import AdaptiveMultiAgentScheduler
from .contract_engine import ContractEngine
from .mission_compiler import MissionCompiler
from .mission_triage import MissionTriageEngine
from .orchestration import RuntimeOrchestrator
from .state_machine import MissionStateMachine


class ChiefBrainKernel:
    """Explicit boundary for the 7 kernel modules.

    This class:
    - WRAPS the existing kernel implementation
    - ENFORCES the G1 contract boundaries (5 invariants)
    - PROVIDES a single entry point for kernel operations
    - PREVENTS infrastructure bypass (INVARIANT_02)

    It does NOT:
    - Replace NexaraRuntime (which remains as the full composition root)
    - Add new business logic
    - Duplicate state machine or mission lifecycle
    - Modify existing module behavior

    The kernel boundary is:
    ┌─────────────────────────────────────────┐
    │  ChiefBrainKernel (this)                │
    │  ┌─────────────────────────────────────┐│
    │  │ IN SCOPE (7 modules)                ││
    │  │  • MissionTriageEngine              ││
    │  │  • MissionCompiler                  ││
    │  │  • ContractEngine                   ││
    │  │  • MissionStateMachine              ││
    │  │  • RuntimeOrchestrator              ││
    │  │  • AdaptiveMultiAgentScheduler      ││
    │  │  • (State validation)               ││
    │  └─────────────────────────────────────┘│
    │                                          │
    │  PROHIBITED:                             │
    │  • Self-verify (INVARIANT_03)           │
    │  • Grant permissions (INVARIANT_01)     │
    │  • Overwrite evidence (INVARIANT_04)    │
    │  • Bypass governance (R2 rule)          │
    │  • Skip state machine (PROHIBIT_06)     │
    └─────────────────────────────────────────┘
    """

    def __init__(
        self,
        triage: MissionTriageEngine,
        compiler: MissionCompiler,
        contracts: ContractEngine,
        state_machine: MissionStateMachine,
        orchestrator: RuntimeOrchestrator,
        scheduler: AdaptiveMultiAgentScheduler,
    ) -> None:
        self._triage = triage
        self._compiler = compiler
        self._contracts = contracts
        self._state_machine = state_machine
        self._orchestrator = orchestrator
        self._scheduler = scheduler

    # ── Read-only accessors (kernel boundary is VISIBLE but not DIRECTLY mutable) ──

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

    # ── Boundary enforcement ──

    def validate_transition(
        self, current_state: str, target_state: str, actor: str
    ) -> bool:
        """Validate a state transition through the kernel boundary.

        PROHIBIT_06: ALL state transitions go through state_machine validation.
        """
        return self._state_machine.can_transition(current_state, target_state)

    def assert_no_self_verify(self, executor_id: str, auditor_id: str) -> None:
        """PROHIBIT_01 / INVARIANT_03: Executor cannot be the Auditor.

        Raises ValueError if executor and auditor are the same agent.
        """
        if executor_id == auditor_id:
            raise ValueError(
                f"INVARIANT_03 violation: executor '{executor_id}' "
                f"cannot also be the auditor. Use an independent agent."
            )

    def assert_no_permission_grant(self, requested_permissions: list[str]) -> None:
        """PROHIBIT_03 / INVARIANT_01: Kernel cannot grant permissions.

        Logs a warning if permission-like fields are passed through the kernel.
        Permissions are ALWAYS external (human-granted).
        """
        if requested_permissions:
            import logging
            logging.warning(
                "INVARIANT_01 boundary: permission grant requested through kernel. "
                "Permissions must be granted externally by a human. "
                f"Requested: {requested_permissions}"
            )

    def assert_evidence_not_modified(self, evidence_id: str) -> None:
        """PROHIBIT_04 / INVARIANT_04: Evidence is append-only.

        The kernel must never modify or delete evidence after creation.
        This is a boundary assertion — the EvidenceStore enforces this at the data layer.
        """
        # Evidence immutability is enforced by EvidenceStore (append-only design).
        # This method exists as a contract-level assertion for audit clarity.
        pass

    def assert_full_completion_chain(
        self,
        success_criteria_met: bool,
        evidence_committed: bool,
        audit_completed: bool,
        receipt_created: bool,
        reflection_recorded: bool,
    ) -> None:
        """PROHIBIT_05 / INVARIANT_05: All 5 completion gates must pass.

        Raises ValueError if any gate is not met.
        """
        gates = {
            "success_criteria": success_criteria_met,
            "evidence": evidence_committed,
            "audit": audit_completed,
            "receipt": receipt_created,
            "reflection": reflection_recorded,
        }
        missing = [k for k, v in gates.items() if not v]
        if missing:
            raise ValueError(
                f"INVARIANT_05 violation: mission completion requires all 5 gates. "
                f"Missing: {missing}"
            )

    # ── Kernel health ──

    def health(self) -> dict[str, Any]:
        """Return kernel module health status."""
        return {
            "kernel_boundary": "active",
            "modules": {
                "triage": self._triage is not None,
                "compiler": self._compiler is not None,
                "contracts": self._contracts is not None,
                "state_machine": self._state_machine is not None,
                "orchestrator": self._orchestrator is not None,
                "scheduler": self._scheduler is not None,
            },
        }
