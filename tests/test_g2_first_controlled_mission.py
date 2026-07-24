"""G2-D: First Controlled Mission — end-to-end kernel boundary integration test.

Updated for Phase 3 ChiefBrainKernel enforcement boundary API.
"""
from __future__ import annotations

import pytest

from nexara_prime.chief_brain_kernel import ChiefBrainKernel
from nexara_prime.contract_engine import ContractEngine
from nexara_prime.kernel_boundary import GovernanceViolation, KernelBoundaryViolation
from nexara_prime.mission_compiler import MissionCompiler
from nexara_prime.mission_triage import MissionTriageEngine
from nexara_prime.models import MissionSpec
from nexara_prime.state_machine import MissionStateMachine


class TestFirstControlledMission:
    """G2-D: A complete mission lifecycle through the kernel boundary."""

    @pytest.fixture
    def kernel(self) -> ChiefBrainKernel:
        from nexara_prime.events import EventBus
        from nexara_prime.evidence import EvidenceStore
        from nexara_prime.governance import ApprovalEngine, PolicyEngine

        class FakeStore:
            def execute(self, *a, **kw): pass
            def executemany(self, *a, **kw): pass
            def fetchone(self, *a, **kw): return None
            def fetchall(self, *a, **kw): return []
            def commit(self, *a, **kw): pass
            def close(self, *a, **kw): pass

        store = FakeStore()
        events = EventBus(store)  # type: ignore[arg-type]
        evidence = EvidenceStore(store, events)  # type: ignore[arg-type]
        policy = PolicyEngine()
        approvals = ApprovalEngine(store, events)  # type: ignore[arg-type]

        return ChiefBrainKernel(
            triage=MissionTriageEngine(),
            compiler=MissionCompiler(),
            contracts=ContractEngine(),
            state_machine=MissionStateMachine(events, evidence),
            orchestrator=None,  # type: ignore[arg-type]
            scheduler=None,  # type: ignore[arg-type]
            policy=policy,
            approvals=approvals,
        )

    def test_kernel_health_all_modules_present(self, kernel: ChiefBrainKernel) -> None:
        h = kernel.health()
        assert h["kernel_boundary"] == "active"
        modules = h["modules"]
        assert modules["triage"]
        assert modules["compiler"]
        assert modules["contracts"]
        assert modules["state_machine"]

    def test_kernel_accessors_return_modules(self, kernel: ChiefBrainKernel) -> None:
        assert isinstance(kernel.triage, MissionTriageEngine)
        assert isinstance(kernel.compiler, MissionCompiler)
        assert isinstance(kernel.contracts, ContractEngine)
        assert isinstance(kernel.state_machine, MissionStateMachine)

    def test_state_transition_validation(self, kernel: ChiefBrainKernel) -> None:
        can = kernel.validate_transition("Intent", "Context")
        assert can
        can = kernel.validate_transition("Intent", "Completed")
        assert not can

    def test_invariant_03_no_self_verify_enforced(self, kernel: ChiefBrainKernel) -> None:
        with pytest.raises(KernelBoundaryViolation, match="INVARIANT_03"):
            kernel.assert_no_self_verify("agent_7", "agent_7")
        kernel.assert_no_self_verify("executor_1", "auditor_2")

    def test_invariant_05_full_completion_chain_enforced(self, kernel: ChiefBrainKernel) -> None:
        kernel.assert_full_completion_chain(True, True, True, True, True)
        with pytest.raises(KernelBoundaryViolation, match="INVARIANT_05"):
            kernel.assert_full_completion_chain(True, True, False, True, True)
        with pytest.raises(KernelBoundaryViolation, match="INVARIANT_05"):
            kernel.assert_full_completion_chain(True, False, True, True, True)
        with pytest.raises(KernelBoundaryViolation, match="INVARIANT_05"):
            kernel.assert_full_completion_chain(False, False, False, False, False)

    def test_invariant_01_no_permission_grant_raises(self, kernel: ChiefBrainKernel) -> None:
        with pytest.raises(GovernanceViolation, match="INVARIANT_01"):
            kernel.assert_no_permission_grant(["admin", "write"])
        kernel.assert_no_permission_grant([])

    def test_mission_compiler_creates_spec(self, kernel: ChiefBrainKernel) -> None:
        spec = kernel.compiler.compile("Analyze repository security")
        assert isinstance(spec, MissionSpec)
        assert spec.mission_id
        assert "security" in spec.objective.lower()

    def test_contract_engine_creates_work_contract(self, kernel: ChiefBrainKernel) -> None:
        spec = kernel.compiler.compile("Deploy configuration update")
        contract = kernel.contracts.create(spec)
        assert contract is not None
        assert contract.mission_id == spec.mission_id

    def test_triage_engine_returns_decision(self, kernel: ChiefBrainKernel) -> None:
        result = kernel.triage.triage(
            intent="Deploy to production",
            context="production environment with user data",
            requested_outcome="Successful zero-downtime deployment",
            tool_requirements=["deploy", "restart_service"],
            data_sensitivity="high",
            external_side_effects=True,
            reversibility=False,
        )
        assert result is not None
        assert result.risk_score > 0.3
        assert result.recommended_mode in {"S2", "S3"}


class TestKernelProhibitedBehaviors:
    """Each PROHIBIT rule from the kernel contract must be enforceable."""

    @pytest.fixture
    def kernel(self) -> ChiefBrainKernel:
        from nexara_prime.events import EventBus
        from nexara_prime.evidence import EvidenceStore
        from nexara_prime.governance import ApprovalEngine, PolicyEngine

        class FakeStore:
            def execute(self, *a, **kw): pass
            def executemany(self, *a, **kw): pass
            def fetchone(self, *a, **kw): return None
            def fetchall(self, *a, **kw): return []
            def commit(self, *a, **kw): pass
            def close(self, *a, **kw): pass

        store = FakeStore()
        events = EventBus(store)  # type: ignore[arg-type]
        evidence = EvidenceStore(store, events)  # type: ignore[arg-type]
        policy = PolicyEngine()
        approvals = ApprovalEngine(store, events)  # type: ignore[arg-type]

        return ChiefBrainKernel(
            triage=MissionTriageEngine(),
            compiler=MissionCompiler(),
            contracts=ContractEngine(),
            state_machine=MissionStateMachine(events, evidence),
            orchestrator=None,  # type: ignore[arg-type]
            scheduler=None,  # type: ignore[arg-type]
            policy=policy,
            approvals=approvals,
        )

    def test_prohibit_01_no_self_verify(self, kernel: ChiefBrainKernel) -> None:
        with pytest.raises(KernelBoundaryViolation):
            kernel.assert_no_self_verify("same", "same")

    def test_prohibit_03_no_permission_grant(self, kernel: ChiefBrainKernel) -> None:
        with pytest.raises(GovernanceViolation):
            kernel.assert_no_permission_grant(["admin"])

    def test_prohibit_04_evidence_not_modified(self, kernel: ChiefBrainKernel) -> None:
        with pytest.raises(KernelBoundaryViolation):
            kernel.assert_evidence_not_modified("ev_1", "")

    def test_prohibit_05_full_completion_chain(self, kernel: ChiefBrainKernel) -> None:
        with pytest.raises(KernelBoundaryViolation):
            kernel.assert_full_completion_chain(True, False, True, True, True)

    def test_prohibit_06_state_machine_validation(self, kernel: ChiefBrainKernel) -> None:
        can = kernel.validate_transition("Intent", "Completed")
        assert not can
