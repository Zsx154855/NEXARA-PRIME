"""V2 Runtime — checkpoint_done() and release() coverage gap fill.

checkpoint_done() was zero-coverage (untested); release() was zero-coverage
(untested).  Both are simple methods that were overlooked during the V2
hardening sprint.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from nexara_prime.capabilities import CapabilityRegistry
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.models import AgentAssignment, Persona, RuntimeRole
from nexara_prime.recovery import DurableRecovery
from nexara_prime.scheduler import AdaptiveScheduler


# ── checkpoint_done() tests ────────────────────────────────────────────

class TestCheckpointDone:
    """Direct unit tests for DurableRecovery.checkpoint_done()."""

    @staticmethod
    def _make_recovery(db_dir: Path | None = None) -> tuple[DurableRecovery, SQLiteStore]:
        db_path = Path(tempfile.mkdtemp()) / "test.db" if db_dir is None else db_dir / "test.db"
        store = SQLiteStore(db_path)
        events = EventBus(store)
        recovery = DurableRecovery(store, events)
        return recovery, store

    def test_returns_false_when_no_checkpoint_exists(self) -> None:
        recovery, _ = self._make_recovery()
        assert recovery.checkpoint_done("mission_x", "step_execute") is False

    def test_returns_true_after_checkpoint_created(self) -> None:
        recovery, _ = self._make_recovery()
        recovery.checkpoint("mission_1", "step_execute", "trace_001")
        assert recovery.checkpoint_done("mission_1", "step_execute") is True

    def test_different_mission_not_confused(self) -> None:
        recovery, _ = self._make_recovery()
        recovery.checkpoint("mission_1", "step_execute", "trace_001")
        # Same step, different mission → not done
        assert recovery.checkpoint_done("mission_2", "step_execute") is False

    def test_different_step_not_confused(self) -> None:
        recovery, _ = self._make_recovery()
        recovery.checkpoint("mission_1", "step_execute", "trace_001")
        # Same mission, different step → not done
        assert recovery.checkpoint_done("mission_1", "step_verify") is False

    def test_exact_match_required(self) -> None:
        """checkpoint_done must match mission_id AND step exactly."""
        recovery, _ = self._make_recovery()
        recovery.checkpoint("m1", "s1", "t1")
        assert recovery.checkpoint_done("m1", "s1") is True
        assert recovery.checkpoint_done("m1", "s2") is False
        assert recovery.checkpoint_done("m2", "s1") is False

    def test_multiple_checkpoints_all_detectable(self) -> None:
        recovery, _ = self._make_recovery()
        for step in ["compile", "simulate", "execute", "verify"]:
            recovery.checkpoint("mission_1", step, f"trace_{step}")
        for step in ["compile", "simulate", "execute", "verify"]:
            assert recovery.checkpoint_done("mission_1", step) is True
        assert recovery.checkpoint_done("mission_1", "eval") is False

    def test_idempotent_checkpoint_still_returns_true(self) -> None:
        """checkpoint() is idempotent; checkpoint_done() returns True even after duplicate call."""
        recovery, _ = self._make_recovery()
        recovery.checkpoint("mission_1", "step_execute", "trace_001")
        # Re-call checkpoint with the same key — should be idempotent
        recovery.checkpoint("mission_1", "step_execute", "trace_002")
        assert recovery.checkpoint_done("mission_1", "step_execute") is True

    def test_persisted_across_re_instantiation(self) -> None:
        """checkpoint_done must survive runtime re-instantiation (shared DB)."""
        db_dir = Path(tempfile.mkdtemp())
        recovery1, _ = self._make_recovery(db_dir)
        recovery1.checkpoint("mission_1", "step_execute", "trace_001")

        # Re-instantiate with same DB
        store2 = SQLiteStore(db_dir / "test.db")
        events2 = EventBus(store2)
        recovery2 = DurableRecovery(store2, events2)
        assert recovery2.checkpoint_done("mission_1", "step_execute") is True

    def test_custom_idempotency_key_respected(self) -> None:
        """checkpoint() with custom idempotency_key; checkpoint_done uses derived key."""
        recovery, _ = self._make_recovery()
        recovery.checkpoint("mission_1", "step_execute", "trace_001", idempotency_key="my_custom_key")
        # Standard key should NOT match
        assert recovery.checkpoint_done("mission_1", "step_execute") is False
        # Direct store lookup with custom key should find it
        assert recovery.store.find_record("checkpoint", "idempotency_key", "my_custom_key") is not None


# ── release() tests ────────────────────────────────────────────────────

def _make_assignment(mission_id: str = "mission_1", role: RuntimeRole = RuntimeRole.EXECUTOR) -> AgentAssignment:
    return AgentAssignment(
        mission_id=mission_id,
        persona=Persona.VERTEX,
        runtime_role=role,
    )


class TestAdaptiveSchedulerRelease:
    """Direct unit tests for AdaptiveScheduler.release()."""

    @staticmethod
    def _make_scheduler() -> tuple[AdaptiveScheduler, CapabilityRegistry]:
        registry = CapabilityRegistry()
        scheduler = AdaptiveScheduler(registry)
        return scheduler, registry

    def test_release_removes_single_assignment(self) -> None:
        scheduler, registry = self._make_scheduler()
        a = _make_assignment()
        registry.mount_for(a.assignment_id, ["skill.evidence", "policy.risk", "model.mock"])
        assert len(registry.mounted(a.assignment_id)) == 3

        scheduler.release([a])
        assert registry.mounted(a.assignment_id) == []

    def test_release_handles_empty_list(self) -> None:
        scheduler, registry = self._make_scheduler()
        scheduler.release([])  # Must not raise

    def test_release_removes_multiple_assignments(self) -> None:
        scheduler, registry = self._make_scheduler()
        a1 = _make_assignment("mission_1", RuntimeRole.EXECUTOR)
        a2 = _make_assignment("mission_2", RuntimeRole.REVIEWER)
        registry.mount_for(a1.assignment_id, ["skill.evidence", "model.mock"])
        registry.mount_for(a2.assignment_id, ["policy.risk"])

        scheduler.release([a1, a2])
        assert registry.mounted(a1.assignment_id) == []
        assert registry.mounted(a2.assignment_id) == []

    def test_release_idempotent(self) -> None:
        scheduler, registry = self._make_scheduler()
        a = _make_assignment()
        registry.mount_for(a.assignment_id, ["skill.evidence"])
        scheduler.release([a])
        scheduler.release([a])  # Second release must not raise
        assert registry.mounted(a.assignment_id) == []

    def test_release_does_not_affect_other_assignments(self) -> None:
        scheduler, registry = self._make_scheduler()
        a1 = _make_assignment("mission_1", RuntimeRole.EXECUTOR)
        a2 = _make_assignment("mission_2", RuntimeRole.REVIEWER)
        registry.mount_for(a1.assignment_id, ["skill.evidence"])
        registry.mount_for(a2.assignment_id, ["policy.risk"])

        scheduler.release([a1])
        assert registry.mounted(a1.assignment_id) == []
        assert len(registry.mounted(a2.assignment_id)) == 1  # a2 untouched

    def test_release_after_schedule_full_cycle(self) -> None:
        """schedule() then release() — validates full adaptive-scheduler lifecycle."""
        from nexara_prime.models import MissionSpec

        scheduler, registry = self._make_scheduler()
        spec = MissionSpec(title="Release lifecycle test", objective="Test release lifecycle", deliverables=["report.md"])
        assignments = scheduler.schedule(spec, provider_name="mock")
        assert len(assignments) >= 6  # At least base 6 roles

        # Verify all are mounted
        for a in assignments:
            assert len(registry.mounted(a.assignment_id)) > 0, f"{a.assignment_id} not mounted"

        scheduler.release(assignments)
        for a in assignments:
            assert registry.mounted(a.assignment_id) == [], f"{a.assignment_id} still mounted after release"

    def test_release_with_same_assignment_twice_in_list(self) -> None:
        """Calling release with the same assignment object twice is harmless."""
        scheduler, registry = self._make_scheduler()
        a = _make_assignment()
        registry.mount_for(a.assignment_id, ["skill.evidence"])
        scheduler.release([a, a])
        assert registry.mounted(a.assignment_id) == []
