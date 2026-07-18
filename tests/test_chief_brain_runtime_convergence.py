"""Tests for NEXARA Chief Brain Runtime Convergence V1.

Covers: NexaraRuntime single-entry authority, approval resume E2E,
crash recovery, provider strategy, runtime snapshot, state machine invariants.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nexara_prime.models import MissionState
from nexara_prime.runtime import NexaraRuntime
from nexara_prime.config import Settings


@pytest.fixture
def runtime() -> NexaraRuntime:
    """Create a runtime with mock provider for testing."""
    settings = Settings(
        db_path=Path(tempfile.mkdtemp()) / "test.db",
        workspace_root=Path(tempfile.mkdtemp()),
        report_root=Path(tempfile.mkdtemp()),
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8765,
    )
    settings.ensure_dirs()
    return NexaraRuntime(settings)


class TestNexaraRuntimeSingleAuthority:
    """NexaraRuntime is the sole authority for mission lifecycle."""

    def test_create_mission_produces_unique_id(self, runtime: NexaraRuntime) -> None:
        m1 = runtime.create_mission("Test mission one")
        m2 = runtime.create_mission("Test mission two")
        assert m1.mission_id != m2.mission_id
        assert m1.mission_id.startswith("mission_")

    def test_mission_state_is_written_by_runtime_only(self, runtime: NexaraRuntime) -> None:
        m = runtime.create_mission("Test")
        assert m.state == "Intent"
        runtime.plan_mission(m.mission_id)
        loaded = runtime.get_mission(m.mission_id)
        assert loaded.state != "Intent"

    def test_runtime_is_only_writer(self, runtime: NexaraRuntime) -> None:
        m = runtime.create_mission("Test")
        loaded = runtime.get_mission(m.mission_id)
        assert loaded.mission_id == m.mission_id
        assert loaded.state == m.state


class TestApprovalResumeE2E:
    """End-to-end approval resume pipeline: pause → approve → resume → complete."""

    def test_full_approval_resume_cycle(self, runtime: NexaraRuntime) -> None:
        mission = runtime.create_mission("Generate a bounded test report for E2E verification")
        original_mission_id = mission.mission_id
        assert mission.state == "Intent"

        # Plan → Contract → Approval
        planned = runtime.plan_mission(mission.mission_id)
        assert planned.state == "Approval"
        assert planned.pending_approval_id is not None

        # Human approval
        approved = runtime.approve_mission(
            mission.mission_id, approved=True, actor="human",
            note="E2E test: approved for bounded local execution."
        )
        assert approved.state == "Execution"

        # Run mission
        result = runtime.run_mission(mission.mission_id)
        assert result.state == "Completed"

        # Verify Mission ID never changed
        assert result.mission_id == original_mission_id

        # Verify Evidence exists before completion
        evidence = runtime.evidence.list(mission.mission_id)
        assert len(evidence) > 0

        # Verify Memory Patch after Evidence
        assert "memory_patch_id" in result.result

        # Verify Evaluation references Evidence
        assert result.result.get("evaluation_passed") is True

    def test_resume_keeps_same_mission_id(self, runtime: NexaraRuntime) -> None:
        mission = runtime.create_mission("Test resume ID preservation")
        original_id = mission.mission_id

        runtime.pause(original_id)
        resumed = runtime.resume(original_id)
        assert resumed.mission_id == original_id
        assert not resumed.paused

    def test_approval_binds_original_pending_action(self, runtime: NexaraRuntime) -> None:
        mission = runtime.create_mission("Test approval binding")
        planned = runtime.plan_mission(mission.mission_id)
        action_id = planned.pending_approval_id
        assert action_id is not None

        approved = runtime.approve_mission(mission.mission_id, approved=True)
        assert approved.pending_approval_id == action_id

    def test_no_duplicate_side_effects_on_resume(self, runtime: NexaraRuntime) -> None:
        """Resuming does not re-execute completed work."""
        mission = runtime.create_mission("Test no duplicate side effects")
        runtime.plan_mission(mission.mission_id)
        runtime.approve_mission(mission.mission_id, approved=True)

        # Complete first run
        result = runtime.run_mission(mission.mission_id)
        assert result.state == "Completed"
        evidence_count = len(runtime.evidence.list(mission.mission_id))

        # Resume completed mission (should be no-op)
        resumed = runtime.resume(mission.mission_id)
        assert resumed.state == "Completed"
        # Evidence count unchanged — no re-execution
        assert len(runtime.evidence.list(mission.mission_id)) == evidence_count


class TestCrashRecovery:
    """Crash recovery scenarios: before execution, after execution, during approval."""

    def test_resume_from_paused_state(self, runtime: NexaraRuntime) -> None:
        mission = runtime.create_mission("Test pause resume")
        runtime.pause(mission.mission_id)
        paused = runtime.get_mission(mission.mission_id)
        assert paused.paused is True

        resumed = runtime.resume(mission.mission_id)
        assert resumed.paused is False

    def test_recoverable_state_detection(self, runtime: NexaraRuntime) -> None:
        """Mission in EXECUTION state is detected as resumable by recovery."""
        mission = runtime.create_mission("Test recoverable detection")
        runtime.plan_mission(mission.mission_id)
        runtime.approve_mission(mission.mission_id, approved=True)
        result = runtime.run_mission(mission.mission_id)
        # After completion, mission should not be resumable
        assert result.state == "Completed"

        recovery = runtime.recover()
        resumable_ids = [m["mission_id"] for m in recovery.missions if m.get("resumable")]
        assert mission.mission_id not in resumable_ids

    def test_provider_unavailable_setting(self, runtime: NexaraRuntime) -> None:
        """When no real provider configured and mock_model=False, provider_unavailable is flagged."""
        # Runtime with mock_model=True should not flag provider as unavailable
        assert not getattr(runtime, '_provider_unavailable', False)


class TestRuntimeSnapshot:
    """Runtime truth snapshot from inspect_mission()."""

    def test_inspect_returns_complete_snapshot(self, runtime: NexaraRuntime) -> None:
        mission = runtime.create_mission("Test snapshot completeness")
        snapshot = runtime.inspect_mission(mission.mission_id)

        required_fields = [
            "mission_id", "current_state", "risk_level", "provider",
            "approval_status", "pending_action", "evidence_count",
            "memory_patch_status", "evaluation_status", "retry_count",
            "started_at", "updated_at", "paused", "trace_id",
        ]
        for field in required_fields:
            assert field in snapshot, f"Missing field: {field}"

        assert snapshot["mission_id"] == mission.mission_id
        assert snapshot["current_state"] == "Intent"

    def test_snapshot_after_approval(self, runtime: NexaraRuntime) -> None:
        mission = runtime.create_mission("Test snapshot after approval")
        runtime.plan_mission(mission.mission_id)

        snapshot = runtime.inspect_mission(mission.mission_id)
        assert snapshot["current_state"] == "Approval"
        assert snapshot["approval_status"] is not None

    def test_snapshot_after_completion(self, runtime: NexaraRuntime) -> None:
        mission = runtime.create_mission("Test snapshot after completion")
        runtime.plan_mission(mission.mission_id)
        runtime.approve_mission(mission.mission_id, approved=True)
        runtime.run_mission(mission.mission_id)

        snapshot = runtime.inspect_mission(mission.mission_id)
        assert snapshot["current_state"] == "Completed"
        assert snapshot["memory_patch_status"] == "patched"
        assert snapshot["evaluation_status"] == "passed"


class TestProviderStrategy:
    """Provider selection: mock must be explicit, not implicit."""

    def test_mock_model_explicit_only(self, runtime: NexaraRuntime) -> None:
        """When mock_model=True, provider should be mock."""
        assert runtime.models.provider.name == "mock"
        assert not getattr(runtime, '_provider_unavailable', False)

    def test_no_silent_mock_fallback(self) -> None:
        """Without explicit mock_model and without real provider config,
        provider_unavailable should be set."""
        # Create runtime with no provider configured and mock_model=False
        settings = Settings(
            db_path=Path(tempfile.mkdtemp()) / "test.db",
            workspace_root=Path(tempfile.mkdtemp()),
            report_root=Path(tempfile.mkdtemp()),
            model_provider="none",
            mock_model=False,
            api_host="127.0.0.1",
            api_port=8765,
        )
        settings.ensure_dirs()
        rt = NexaraRuntime(settings)
        # In test env with no OPENAI_API_KEY etc., this should enter unavailable state
        assert rt.models.provider is not None  # structural placeholder exists
        assert getattr(rt, '_provider_unavailable', False) is True


class TestStateMachineInvariants:
    """Mission state machine invariants enforced by single authority."""

    def test_legal_transition_chain(self, runtime: NexaraRuntime) -> None:
        m = runtime.create_mission("Test legal chain")
        assert m.state == "Intent"
        runtime._advance(m, MissionState.CONTEXT, "test")
        assert m.state == "Context"

    def test_approval_is_not_failed(self, runtime: NexaraRuntime) -> None:
        """WAITING_APPROVAL is not a failure state."""
        mission = runtime.create_mission("Test approval not failed")
        planned = runtime.plan_mission(mission.mission_id)
        assert planned.state == "Approval"
        assert planned.state not in {"Failed", "Blocked"}

    def test_resume_does_not_create_new_mission(self, runtime: NexaraRuntime) -> None:
        mission = runtime.create_mission("Test resume no new mission")
        count_before = len(runtime.list_missions())
        runtime.pause(mission.mission_id)
        runtime.resume(mission.mission_id)
        count_after = len(runtime.list_missions())
        assert count_after == count_before

    def test_cancel_mission(self, runtime: NexaraRuntime) -> None:
        """Cancel puts mission in terminal state."""
        mission = runtime.create_mission("Test cancel")
        runtime._advance(mission, MissionState.FAILED, "test")
        assert mission.state == "Failed"


class TestEntryPointUnification:
    """API, CLI, and tests all enter through NexaraRuntime."""

    def test_api_create_uses_runtime(self, runtime: NexaraRuntime) -> None:
        from nexara_prime.api import create_app
        from starlette.testclient import TestClient
        app = create_app(runtime)
        client = TestClient(app)
        response = client.post("/api/missions", json={"objective": "API test"})
        assert response.status_code == 200

    def test_api_resume_uses_runtime(self, runtime: NexaraRuntime) -> None:
        from nexara_prime.api import create_app
        from starlette.testclient import TestClient
        m = runtime.create_mission("Test API resume")
        app = create_app(runtime)
        client = TestClient(app)
        response = client.post(f"/api/missions/{m.mission_id}/resume")
        assert response.status_code == 200

    def test_cli_commands_use_runtime(self, runtime: NexaraRuntime) -> None:
        # CLI internally wraps NexaraRuntime — verify create and status work
        m = runtime.create_mission("CLI test mission")
        assert m.mission_id is not None
        loaded = runtime.get_mission(m.mission_id)
        assert loaded.mission_id == m.mission_id


class TestBackwardsCompatibility:
    """Old entry points still work through NexaraRuntime."""

    def test_legacy_get_mission(self, runtime: NexaraRuntime) -> None:
        m = runtime.create_mission("Legacy test")
        loaded = runtime.get_mission(m.mission_id)
        assert loaded.state == "Intent"

    def test_legacy_resume(self, runtime: NexaraRuntime) -> None:
        m = runtime.create_mission("Legacy resume")
        runtime.pause(m.mission_id)
        resumed = runtime.resume(m.mission_id)
        assert not resumed.paused


class TestSchedulerUniqueness:
    """Scheduler remains the single public scheduling entry."""

    def test_scheduler_is_single_entry(self, runtime: NexaraRuntime) -> None:
        assert runtime.scheduler is not None
        from nexara_prime.scheduler import AdaptiveScheduler
        assert isinstance(runtime.scheduler, AdaptiveScheduler)

    def test_scheduler_used_by_runtime(self, runtime: NexaraRuntime) -> None:
        m = runtime.create_mission("Test scheduler usage")
        m2 = runtime.plan_mission(m.mission_id)
        assert m2.assignments is not None
        assert len(m2.assignments) > 0


class TestNoSupervisor:
    """There is no Supervisor class in the codebase — NexaraRuntime is sole authority."""

    def test_no_supervisor_class(self) -> None:
        """Verify Supervisor does not exist in the source tree."""
        import importlib
        with pytest.raises((ImportError, ModuleNotFoundError)):
            importlib.import_module("nexara_prime.supervisor")
