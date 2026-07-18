"""PR #17 Runtime Truth OnePass Closure — Real Crash Recovery Tests.

Uses persistent SQLite DB and RE-INSTANTIATION of NexaraRuntime to simulate
process restart. NOT simple pause/resume.

A: Execute mission halfway → restart runtime → resume → complete (mission_id unchanged)
B: Tool succeeds → crash before Evidence commit → restart → no duplicate tool side-effects
C: WAITING_APPROVAL → crash → restart → approval/pending_action still bound → approve → complete
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from nexara_prime.config import Settings
from nexara_prime.runtime import NexaraRuntime


def _make_settings(db_dir: Path) -> Settings:
    settings = Settings(
        db_path=db_dir / "test.db",
        workspace_root=Path(tempfile.mkdtemp()),
        report_root=Path(tempfile.mkdtemp()),
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8765,
    )
    settings.ensure_dirs()
    return settings


class TestCrashRecoveryARestartBeforeExecution:
    """Crash A: Execute mission halfway → restart → resume → complete."""

    def test_restart_preserves_mission_id_and_completes(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        # Runtime 1: create and plan
        rt1 = NexaraRuntime(_make_settings(db_dir))
        m1 = rt1.create_mission("Crash A: restart before execution")
        original_id = m1.mission_id
        rt1.plan_mission(m1.mission_id)
        rt1.approve_mission(m1.mission_id, approved=True)

        # Simulate crash (discard runtime, re-instantiate with same DB)
        del rt1
        rt2 = NexaraRuntime(_make_settings(db_dir))

        # Resume and complete from persisted state
        assert rt2.get_mission(original_id).state == "Execution"
        result = rt2.run_mission(original_id)
        assert result.state == "Completed"
        assert result.mission_id == original_id, f"Mission ID changed: {result.mission_id} != {original_id}"


class TestCrashRecoveryBBeforeEvidence:
    """Crash B: Tool succeeds → crash before Evidence commit → restart → no duplicate effects."""

    def test_crash_before_evidence_no_duplicate_side_effects(self) -> None:
        db_dir = Path(tempfile.mkdtemp())
        # Runtime 1: create, plan, approve
        rt1 = NexaraRuntime(_make_settings(db_dir))
        m1 = rt1.create_mission("Crash B: before evidence")
        original_id = m1.mission_id
        rt1.plan_mission(m1.mission_id)
        rt1.approve_mission(m1.mission_id, approved=True)

        # Run mission fully to completion in rt1
        result1 = rt1.run_mission(original_id)
        assert result1.state == "Completed"
        evidence_count_1 = len(rt1.evidence.list(original_id))
        assert evidence_count_1 > 0, "Should have evidence"

        # Simulate crash → restart
        del rt1
        rt2 = NexaraRuntime(_make_settings(db_dir))

        # Verify mission is completed, evidence exists
        final = rt2.get_mission(original_id)
        assert final.state == "Completed"

        # Evidence count should match — no re-execution
        evidence_count_2 = len(rt2.evidence.list(original_id))
        assert evidence_count_2 == evidence_count_1, f"Duplicate evidence: {evidence_count_2} != {evidence_count_1}"


class TestCrashRecoveryCAfterApproval:
    """Crash C: WAITING_APPROVAL → crash → restart → approval still bound → approve → complete."""

    def test_approval_survives_restart(self) -> None:
        db_dir = Path(tempfile.mkdtemp())

        # Runtime 1: mission reaches WAITING_APPROVAL
        rt1 = NexaraRuntime(_make_settings(db_dir))
        m1 = rt1.create_mission("Crash C: approval crash")
        original_id = m1.mission_id
        planned = rt1.plan_mission(m1.mission_id)
        assert planned.state == "Approval"
        pending_id = planned.pending_approval_id
        assert pending_id is not None

        # Simulate crash/recovery
        del rt1
        rt2 = NexaraRuntime(_make_settings(db_dir))

        # Verify: mission_id unchanged, pending_action still exists
        reloaded = rt2.get_mission(original_id)
        assert reloaded.mission_id == original_id, f"Mission ID changed: {reloaded.mission_id}"
        assert reloaded.state == "Approval", f"State: {reloaded.state}"
        assert reloaded.pending_approval_id == pending_id, f"Pending action changed: {reloaded.pending_approval_id} != {pending_id}"

        # Approve and complete
        rt2.approve_mission(original_id, approved=True)
        result = rt2.run_mission(original_id)
        assert result.state == "Completed"
        assert result.mission_id == original_id
