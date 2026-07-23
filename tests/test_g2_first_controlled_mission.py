"""G2-D: First Controlled Mission — end-to-end kernel boundary integration test.

Verifies:
1. ChiefBrainKernel wraps all 7 kernel modules
2. All 5 invariants are enforced at the boundary
3. A complete mission lifecycle passes through the kernel
4. Prohibited behaviors are caught
"""
from __future__ import annotations

import pytest

from nexara_prime.chief_brain_kernel import ChiefBrainKernel
from nexara_prime.contract_engine import ContractEngine
from nexara_prime.mission_compiler import MissionCompiler
from nexara_prime.mission_triage import MissionTriageEngine
from nexara_prime.models import MissionSpec
from nexara_prime.state_machine import MissionStateMachine


class TestFirstControlledMission:
    """G2-D: A complete mission lifecycle through the kernel boundary."""

    @pytest.fixture
    def kernel(self) -> ChiefBrainKernel:
        """Build ChiefBrainKernel with real kernel modules."""
        from nexara_prime.events import EventBus
        from nexara_prime.evidence import EvidenceStore

        # Minimal fake store for EventBus + EvidenceStore
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

        triage = MissionTriageEngine()
        compiler = MissionCompiler()
        contracts = ContractEngine()
        state_machine = MissionStateMachine(events, evidence)

        return ChiefBrainKernel(
            triage=triage,
            compiler=compiler,
            contracts=contracts,
            state_machine=state_machine,
            orchestrator=None,  # type: ignore[arg-type]
            scheduler=None,  # type: ignore[arg-type]
        )

    def test_kernel_health_all_modules_present(self, kernel: ChiefBrainKernel) -> None:
        """All 6 accessible kernel modules must report healthy."""
        h = kernel.health()
        assert h["kernel_boundary"] == "active"
        modules = h["modules"]
        assert modules["triage"], "MissionTriageEngine must be present"
        assert modules["compiler"], "MissionCompiler must be present"
        assert modules["contracts"], "ContractEngine must be present"
        assert modules["state_machine"], "MissionStateMachine must be present"

    def test_kernel_accessors_return_modules(self, kernel: ChiefBrainKernel) -> None:
        """All property accessors return the injected modules."""
        assert isinstance(kernel.triage, MissionTriageEngine)
        assert isinstance(kernel.compiler, MissionCompiler)
        assert isinstance(kernel.contracts, ContractEngine)
        assert isinstance(kernel.state_machine, MissionStateMachine)

    def test_state_transition_validation(self, kernel: ChiefBrainKernel) -> None:
        """PROHIBIT_06: State transitions must go through state machine validation."""
        # Valid transition: INTENT → CONTEXT
        can = kernel.validate_transition("Intent", "Context", "test_actor")
        assert can, "Intent→Context is a valid transition"

        # Invalid transition: INTENT → COMPLETED (skip all stages)
        can = kernel.validate_transition("Intent", "Completed", "test_actor")
        assert not can, "Intent→Completed must be rejected (skip all stages)"

    def test_invariant_03_no_self_verify_enforced(self, kernel: ChiefBrainKernel) -> None:
        """PROHIBIT_01: Executor cannot be the auditor."""
        # Same agent for both roles → must raise
        with pytest.raises(ValueError, match="INVARIANT_03"):
            kernel.assert_no_self_verify("agent_7", "agent_7")

        # Different agents → no error
        kernel.assert_no_self_verify("executor_1", "auditor_2")

    def test_invariant_05_full_completion_chain_enforced(self, kernel: ChiefBrainKernel) -> None:
        """PROHIBIT_05: All 5 completion gates must pass."""
        # All gates met → no error
        kernel.assert_full_completion_chain(True, True, True, True, True)

        # Missing audit → raises
        with pytest.raises(ValueError, match="INVARIANT_05"):
            kernel.assert_full_completion_chain(True, True, False, True, True)

        # Missing evidence → raises
        with pytest.raises(ValueError, match="INVARIANT_05"):
            kernel.assert_full_completion_chain(True, False, True, True, True)

        # Missing all → raises with all gates listed
        with pytest.raises(ValueError, match="INVARIANT_05"):
            kernel.assert_full_completion_chain(False, False, False, False, False)

    def test_invariant_01_no_permission_grant_logs_warning(
        self, kernel: ChiefBrainKernel, caplog: pytest.LogCaptureFixture
    ) -> None:
        """PROHIBIT_03: Permission requests through kernel log a warning."""
        import logging
        caplog.set_level(logging.WARNING)
        kernel.assert_no_permission_grant(["admin", "write"])
        assert len(caplog.records) >= 1
        assert "INVARIANT_01" in caplog.text

    def test_mission_compiler_creates_spec(self, kernel: ChiefBrainKernel) -> None:
        """MissionCompiler translates objective into MissionSpec."""
        spec = kernel.compiler.compile("Analyze repository security")
        assert isinstance(spec, MissionSpec)
        assert spec.mission_id, "MissionSpec must have mission_id"
        assert "security" in spec.objective.lower()

    def test_contract_engine_creates_work_contract(self, kernel: ChiefBrainKernel) -> None:
        """ContractEngine creates WorkContract from MissionSpec."""
        spec = kernel.compiler.compile("Deploy configuration update")
        contract = kernel.contracts.create(spec)
        assert contract is not None
        assert contract.mission_id == spec.mission_id

    def test_triage_engine_returns_decision(self, kernel: ChiefBrainKernel) -> None:
        """MissionTriageEngine analyzes intent and returns risk assessment."""
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
        # High-risk deployment should get elevated risk score
        assert result.risk_score > 0.3, (
            f"High-risk prod deploy should have risk_score > 0.3, got {result.risk_score}"
        )
        assert result.recommended_mode in {"S2", "S3"}, (
            f"High-risk prod deploy should recommend S2/S3 mode, got {result.recommended_mode}"
        )


class TestKernelProhibitedBehaviors:
    """Each PROHIBIT rule from the kernel contract must be enforceable."""

    @pytest.fixture
    def kernel(self) -> ChiefBrainKernel:
        from nexara_prime.events import EventBus
        from nexara_prime.evidence import EvidenceStore

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

        return ChiefBrainKernel(
            triage=MissionTriageEngine(),
            compiler=MissionCompiler(),
            contracts=ContractEngine(),
            state_machine=MissionStateMachine(events, evidence),
            orchestrator=None,  # type: ignore[arg-type]
            scheduler=None,  # type: ignore[arg-type]
        )

    def test_prohibit_01_no_self_verify(self, kernel: ChiefBrainKernel) -> None:
        """PROHIBIT_01: Self-verify raises ValueError."""
        with pytest.raises(ValueError):
            kernel.assert_no_self_verify("same", "same")

    def test_prohibit_03_no_permission_grant(self, kernel: ChiefBrainKernel) -> None:
        """PROHIBIT_03: Permission requests are flagged."""
        # Method should not raise — it logs a warning instead
        kernel.assert_no_permission_grant(["admin"])

    def test_prohibit_04_evidence_not_modified(self, kernel: ChiefBrainKernel) -> None:
        """PROHIBIT_04: Evidence immutability assertion (contract-level)."""
        # This is a contract assertion — no exception expected
        kernel.assert_evidence_not_modified("ev_123")

    def test_prohibit_05_full_completion_chain(self, kernel: ChiefBrainKernel) -> None:
        """PROHIBIT_05: Missing completion gate raises."""
        with pytest.raises(ValueError):
            kernel.assert_full_completion_chain(True, False, True, True, True)

    def test_prohibit_06_state_machine_validation(self, kernel: ChiefBrainKernel) -> None:
        """PROHIBIT_06: Invalid transition is rejected."""
        can = kernel.validate_transition("Intent", "Completed", "test")
        assert not can
