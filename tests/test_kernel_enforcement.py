"""ChiefBrainKernel enforcement boundary tests.

Phase 3: Kernel is the sole Mission Admission Boundary.
"""
from __future__ import annotations

import pytest

from nexara_prime.chief_brain_kernel import ChiefBrainKernel
from nexara_prime.contract_engine import ContractEngine
from nexara_prime.kernel_boundary import (
    ExecutionBoundaryViolation,
    GovernanceViolation,
    KernelAdmissionContext,
    KernelBoundaryViolation,
    KernelExecutionGuard,
)
from nexara_prime.mission_compiler import MissionCompiler
from nexara_prime.mission_triage import MissionTriageEngine
from nexara_prime.state_machine import MissionStateMachine


class FakeStore:
    def execute(self, *a, **kw): return None
    def executemany(self, *a, **kw): pass
    def fetchone(self, *a, **kw): return None
    def fetchall(self, *a, **kw): return []
    def list_records(self, *a, **kw): return []
    def list_record_envelopes(self, *a, **kw): return []
    def commit(self, *a, **kw): pass
    def close(self, *a, **kw): pass


@pytest.fixture
def kernel() -> ChiefBrainKernel:
    from nexara_prime.events import EventBus
    from nexara_prime.evidence import EvidenceStore
    from nexara_prime.governance import ApprovalEngine, PolicyEngine

    store = FakeStore()
    events = EventBus(store)  # type: ignore[arg-type]
    evidence = EvidenceStore(store, events)  # type: ignore[arg-type]
    policy = PolicyEngine()
    approvals = ApprovalEngine(store, events)  # type: ignore[arg-type]
    sm = MissionStateMachine(events, evidence)

    return ChiefBrainKernel(
        triage=MissionTriageEngine(),
        compiler=MissionCompiler(),
        contracts=ContractEngine(),
        state_machine=sm,
        orchestrator=None,  # type: ignore[arg-type]
        scheduler=None,  # type: ignore[arg-type]
        policy=policy,
        approvals=approvals,
    )


# ═══ Admission Tests ═══

class TestKernelAdmission:
    def test_complete_admission_succeeds(self, kernel: ChiefBrainKernel) -> None:
        ctx = kernel.submit("m1", "test_caller", contract_verified=True,
                            governance_approved=True, state_valid=True,
                            evidence_initialized=True)
        assert ctx is not None
        assert ctx.mission_id == "m1"
        assert ctx.caller == "test_caller"

    def test_missing_governance_blocks(self, kernel: ChiefBrainKernel) -> None:
        with pytest.raises(GovernanceViolation, match="Governance"):
            kernel.submit("m2", "test", contract_verified=True,
                          governance_approved=False, state_valid=True,
                          evidence_initialized=True)

    def test_missing_contract_blocks(self, kernel: ChiefBrainKernel) -> None:
        with pytest.raises(KernelBoundaryViolation, match="Contract"):
            kernel.submit("m3", "test", contract_verified=False,
                          governance_approved=True, state_valid=True,
                          evidence_initialized=True)

    def test_missing_state_validation_blocks(self, kernel: ChiefBrainKernel) -> None:
        with pytest.raises(KernelBoundaryViolation, match="State"):
            kernel.submit("m4", "test", contract_verified=True,
                          governance_approved=True, state_valid=False,
                          evidence_initialized=True)

    def test_missing_evidence_blocks(self, kernel: ChiefBrainKernel) -> None:
        with pytest.raises(KernelBoundaryViolation, match="Evidence"):
            kernel.submit("m5", "test", contract_verified=True,
                          governance_approved=True, state_valid=True,
                          evidence_initialized=False)


# ═══ Invariant Enforcement Tests ═══

class TestInvariantEnforcement:
    def test_self_verify_blocked(self, kernel: ChiefBrainKernel) -> None:
        with pytest.raises(KernelBoundaryViolation, match="INVARIANT_03"):
            kernel.assert_no_self_verify("agent_7", "agent_7")

    def test_self_verify_different_agents_pass(self, kernel: ChiefBrainKernel) -> None:
        kernel.assert_no_self_verify("executor_1", "auditor_2")

    def test_permission_grant_blocked(self, kernel: ChiefBrainKernel) -> None:
        with pytest.raises(GovernanceViolation, match="INVARIANT_01"):
            kernel.assert_no_permission_grant(["admin", "write"])

    def test_permission_grant_empty_pass(self, kernel: ChiefBrainKernel) -> None:
        kernel.assert_no_permission_grant([])

    def test_evidence_modified_without_hash_blocked(self, kernel: ChiefBrainKernel) -> None:
        with pytest.raises(KernelBoundaryViolation, match="INVARIANT_04"):
            kernel.assert_evidence_not_modified("ev_1", "")

    def test_full_completion_chain_missing_audit_blocks(self, kernel: ChiefBrainKernel) -> None:
        with pytest.raises(KernelBoundaryViolation, match="INVARIANT_05"):
            kernel.assert_full_completion_chain(True, True, False, True, True)

    def test_full_completion_chain_all_present_pass(self, kernel: ChiefBrainKernel) -> None:
        kernel.assert_full_completion_chain(True, True, True, True, True)


# ═══ Execution Guard Tests ═══

class TestExecutionGuard:
    def test_guard_blocks_without_admission(self) -> None:
        guard = KernelExecutionGuard()
        with pytest.raises(ExecutionBoundaryViolation, match="No kernel admission"):
            guard.assert_admitted("m99")

    def test_guard_allows_after_admission(self, kernel: ChiefBrainKernel) -> None:
        kernel.submit("m_guard", "test", contract_verified=True,
                      governance_approved=True, state_valid=True,
                      evidence_initialized=True)
        guard_ctx = kernel.guard.assert_admitted("m_guard")
        assert guard_ctx.mission_id == "m_guard"

    def test_guard_blocks_wrong_mission(self, kernel: ChiefBrainKernel) -> None:
        kernel.submit("m_a", "test", contract_verified=True,
                      governance_approved=True, state_valid=True,
                      evidence_initialized=True)
        with pytest.raises(ExecutionBoundaryViolation, match="does not match"):
            kernel.guard.assert_admitted("m_b")


# ═══ KernelAdmissionContext Tests ═══

class TestAdmissionContext:
    def test_context_assert_complete_incomplete_fails(self) -> None:
        ctx = KernelAdmissionContext("m", "test")
        with pytest.raises(KernelBoundaryViolation, match="incomplete"):
            ctx.assert_complete()

    def test_context_assert_complete_all_pass(self) -> None:
        ctx = KernelAdmissionContext("m", "test", contract_verified=True,
                                     authority_verified=True, state_valid=True,
                                     governance_approved=True,
                                     evidence_chain_initialized=True)
        ctx.assert_complete()


# ═══ Singleton Tests ═══

class TestSingletonAuthorities:
    def test_one_nexara_runtime(self) -> None:
        from pathlib import Path
        count = 0
        for f in Path("src/nexara_prime").rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            if "class NexaraRuntime" in f.read_text():
                count += 1
        assert count == 1, "Exactly one NexaraRuntime must exist, found {}".format(count)

    def test_one_mission_state_machine(self) -> None:
        from pathlib import Path
        count = 0
        for f in Path("src/nexara_prime").rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            if "class MissionStateMachine" in f.read_text():
                count += 1
        assert count == 1


# ═══ Kernel boundary types ═══

class TestBoundaryTypes:
    def test_kernel_boundary_violation_is_runtime_error(self) -> None:
        assert issubclass(KernelBoundaryViolation, RuntimeError)

    def test_governance_violation_is_kernel_violation(self) -> None:
        assert issubclass(GovernanceViolation, KernelBoundaryViolation)

    def test_execution_violation_is_kernel_violation(self) -> None:
        assert issubclass(ExecutionBoundaryViolation, KernelBoundaryViolation)
