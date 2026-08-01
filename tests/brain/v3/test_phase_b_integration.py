"""Phase B integration tests — proves execution, approval, recovery, and idempotency.

These tests exercise the remediated governance (fail-closed R2/R3), durable
SQLite runtime (cross-connection persistence), and memory isolation.
"""

from __future__ import annotations

import os
import tempfile


from nexara_prime.brain.governance.autonomous_governance import (
    AuthorityEngine, ApprovalOrchestrator, PolicyRuntime,
)
from nexara_prime.brain.runtime.persistent_runtime import (
    StateManager, RecoveryEngine, Checkpoint,
)
from nexara_prime.models import new_id


class TestPhaseBIntegration:
    """Tests that prove the Phase B closure requirements."""

    def test_b1_readonly_audit_authorized(self) -> None:
        """B1: R0 read-only operations are auto-authorized."""
        ae = AuthorityEngine()
        result = ae.authorize("R0", "executor", "read_file")
        assert result["authorized"] is True
        assert result["can_execute"] is True
        assert result["can_plan"] is True

    def test_b2_r3_denied_before_approval(self) -> None:
        """B2: R3 deploy is denied without approval (fail-closed)."""
        ae = AuthorityEngine()
        result = ae.authorize("R3", "executor", "deploy")
        assert result["authorized"] is False
        assert result["can_execute"] is False
        assert result["can_plan"] is True  # planning allowed
        assert result["can_dry_run"] is True  # dry-run allowed

    def test_b2_r3_approved_with_matching_decision(self) -> None:
        """B2: R3 deploy is authorized after matching approval."""
        ao = ApprovalOrchestrator()
        d = ao.request("mis-1", "proj-1", "R3", "deploy", resource="main")
        assert d.status == "pending"
        approved = ao.approve(d.decision_id, "human-operator")
        assert approved is not None
        assert approved.status == "approved"
        verify = ao.verify(d.decision_id, mission_id="mis-1", project_id="proj-1",
                          action="deploy", resource="main")
        assert verify["authorized"] is True

    def test_b2_policy_r3_blocked_without_decision(self) -> None:
        """B2: PolicyRuntime blocks R3 without decision_id."""
        pr = PolicyRuntime()
        result = pr.enforce("R3", "deploy", ["deploy"], [])
        assert result["allowed"] is False
        assert "missing_decision_id" in result["reason"]

    def test_b2_policy_r3_allowed_with_valid_decision(self) -> None:
        """B2: PolicyRuntime allows R3 with valid approved decision."""
        ao = ApprovalOrchestrator()
        pr = PolicyRuntime()
        pr.bind_orchestrator(ao)
        d = ao.request("mis-2", "proj-2", "R3", "deploy", resource="main")
        ao.approve(d.decision_id, "human-operator")
        result = pr.enforce("R3", "deploy", ["deploy"], [], decision_id=d.decision_id,
                           mission_id="mis-2", project_id="proj-2", resource="main")
        assert result["allowed"] is True

    def test_b2_approval_replay_blocked(self) -> None:
        """B2: Consumed approval cannot be replayed."""
        ao = ApprovalOrchestrator()
        d = ao.request("mis-3", "proj-3", "R3", "deploy")
        ao.approve(d.decision_id, "human")
        ao.consume(d.decision_id)
        verify = ao.verify(d.decision_id, mission_id="mis-3", project_id="proj-3",
                          action="deploy")
        assert verify["authorized"] is False

    def test_b3_checkpoint_persists_across_connections(self) -> None:
        """B3: Checkpoint survives closing and reopening StateManager."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            sm1 = StateManager(db_path=db_path)
            cp = Checkpoint(
                checkpoint_id=new_id("cp"), mission_id="b3-mis", project_id="proj-1",
                run_id=new_id("run"), trace_id=new_id("tr"), state="executing",
                step_index=2, completed_actions=["step1"], pending_actions=["step2"],
                idempotency_keys=["ik1"], evidence_head="ev1",
            )
            sm1.save_checkpoint(cp)
            sm1.close()

            sm2 = StateManager(db_path=db_path)
            loaded = sm2.load_checkpoint("b3-mis", "proj-1")
            assert loaded is not None
            assert loaded.state == "executing"
            assert loaded.step_index == 2
            assert loaded.completed_actions == ["step1"]
            assert loaded.idempotency_keys == ["ik1"]
            sm2.close()
        finally:
            os.unlink(db_path)

    def test_b3_idempotency_survives_restart(self) -> None:
        """B3: Idempotency records persist across connections."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            sm1 = StateManager(db_path=db_path)
            assert sm1.record_effect("proj-1", "b3-mis", "write", "ik-001", "h1") is True
            sm1.close()

            sm2 = StateManager(db_path=db_path)
            assert sm2.is_duplicate("proj-1", "b3-mis", "write", "ik-001") is True
            assert sm2.record_effect("proj-1", "b3-mis", "write", "ik-001", "h1") is False
            sm2.close()
        finally:
            os.unlink(db_path)

    def test_b3_recovery_from_checkpoint(self) -> None:
        """B3: RecoveryEngine recovers state from persisted checkpoint."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            sm1 = StateManager(db_path=db_path)
            cp = Checkpoint(new_id("cp"), "b3-rec", "proj-1", new_id("r1"), new_id("t1"), "executing", 3)
            sm1.save_checkpoint(cp)
            sm1.close()

            sm2 = StateManager(db_path=db_path)
            re = RecoveryEngine(sm2)
            assert re.can_recover("b3-rec", "proj-1") is True
            recovered = re.recover("b3-rec", "proj-1")
            assert recovered is not None
            assert recovered.state == "executing"
            sm2.close()
        finally:
            os.unlink(db_path)

    def test_b3_duplicate_side_effect_prevented(self) -> None:
        """B3: Same idempotency key cannot produce duplicate effects."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            sm = StateManager(db_path=db_path)
            key = "b3-dup-key"
            assert sm.record_effect("proj-1", "b3-mis", "write", key, "hash-a") is True
            assert sm.record_effect("proj-1", "b3-mis", "write", key, "hash-a") is False
            assert sm.record_effect("proj-1", "b3-mis", "write", key, "hash-b") is False
            assert sm.is_duplicate("proj-1", "b3-mis", "write", key) is True
            sm.close()
        finally:
            os.unlink(db_path)

    def test_b3_different_project_independent_idempotency(self) -> None:
        """B3: Idempotency is per-project, not global."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            sm = StateManager(db_path=db_path)
            key = "shared-key"
            assert sm.record_effect("proj-A", "mis-1", "write", key, "ha") is True
            assert sm.record_effect("proj-B", "mis-1", "write", key, "hb") is True
            assert sm.is_duplicate("proj-A", "mis-1", "write", key) is True
            assert sm.is_duplicate("proj-B", "mis-1", "write", key) is True
            sm.close()
        finally:
            os.unlink(db_path)
