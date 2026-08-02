"""Phase C integration tests — SovereignExecutionCoordinator, human control, approval.

Tests the coordinator bridging Phase A+B brain modules into product runtime.
All tests use real coordinator, real Phase A+B governance (fail-closed R4),
and SQLite durable state.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from nexara_prime.sovereign_coordinator import (
    ControlAction, ControlRequest, ControlState,
    SovereignExecutionCoordinator,
)


class MockRuntime:
    """Minimal mock of NexaraRuntime for coordinator testing."""

    def __init__(self) -> None:
        self._missions: dict[str, object] = {}
        self._store: object | None = None

    @property
    def store(self) -> object | None:
        return self._store

    def get_mission(self, mission_id: str) -> object:
        if mission_id in self._missions:
            return self._missions[mission_id]
        raise KeyError(mission_id)

    def list_missions(self) -> list[dict[str, str]]:
        return [{"mission_id": mid} for mid in self._missions]


class MockMission:
    def __init__(self, mission_id: str, state: str = "Intent") -> None:
        self.mission_id = mission_id
        self._state = state
        self.risk_level = None

    class _State:
        def __init__(self, value: str) -> None:
            self.value = value

    @property
    def state(self) -> MockMission._State:
        return self._State(self._state)


class TestSovereignCoordinator:
    """Core coordinator functionality."""

    def _coordinator(self) -> SovereignExecutionCoordinator:
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._db_path = self._tmp.name
        return SovereignExecutionCoordinator(MockRuntime(), db_path=self._db_path)

    def _cleanup(self) -> None:
        import os
        if hasattr(self, '_db_path') and os.path.exists(self._db_path):
            os.unlink(self._db_path)

    def test_coordinator_initialization(self) -> None:
        c = self._coordinator()
        assert c is not None
        overview = c.runtime_overview()
        assert "missions_active" in overview
        assert "approvals_pending" in overview
        assert overview["approvals_pending"] == 0
        self._cleanup()

    def test_risk_approval_mapping(self) -> None:
        c = self._coordinator()
        from nexara_prime.brain.governance.autonomous_governance import ApprovalLevel
        assert c.risk_approval_level("R0") == ApprovalLevel.AUTO
        assert c.risk_approval_level("R2") == ApprovalLevel.CONFIRM
        assert c.risk_approval_level("R3") == ApprovalLevel.HUMAN
        assert c.risk_approval_level("R4") == ApprovalLevel.BLOCKED
        self._cleanup()

    def test_compile_mission_r0(self) -> None:
        c = self._coordinator()
        result = c.compile_mission("audit the codebase")
        assert result["risk_level"] == "R0"
        assert result["requires_approval"] is False
        assert result["compiled"] is True
        self._cleanup()

    def test_compile_mission_r3_requires_approval(self) -> None:
        c = self._coordinator()
        from nexara_prime.models import RiskLevel
        result = c.compile_mission("deploy to production", risk=RiskLevel.R3)
        assert result["risk_level"] == "R3"
        assert result["requires_approval"] is True
        assert result["approval_level"] == "human"
        self._cleanup()

    def test_classify_risk_r0_auto(self) -> None:
        c = self._coordinator()
        c._runtime._missions["mis-1"] = MockMission("mis-1", "Intent")
        result = c.classify_risk("mis-1", "read_file")
        assert result["authorized"] is True
        self._cleanup()


class TestApprovalWorkflow:
    """Approval: request → decide → verify."""

    def _coordinator(self) -> SovereignExecutionCoordinator:
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._db_path = self._tmp.name
        return SovereignExecutionCoordinator(MockRuntime(), db_path=self._db_path)

    def _cleanup(self) -> None:
        import os
        if hasattr(self, '_db_path') and os.path.exists(self._db_path):
            os.unlink(self._db_path)

    def test_request_creates_pending(self) -> None:
        c = self._coordinator()
        req = c.request_approval("mis-1", "proj-1", "R3", "deploy", resource="main")
        assert req["status"] == "pending"
        assert "decision_id" in req
        self._cleanup()

    def test_approve_decision(self) -> None:
        c = self._coordinator()
        req = c.request_approval("mis-1", "proj-1", "R2", "modify")
        result = c.decide_approval(req["decision_id"], "approved", "human-op")
        assert result["ok"] is True
        self._cleanup()

    def test_reject_decision(self) -> None:
        c = self._coordinator()
        req = c.request_approval("mis-1", "proj-1", "R2", "modify")
        result = c.decide_approval(req["decision_id"], "rejected", "human-op")
        assert result["ok"] is True
        assert result["status"] == "rejected"
        self._cleanup()

    def test_revoke_after_approve(self) -> None:
        c = self._coordinator()
        req = c.request_approval("mis-1", "proj-1", "R3", "deploy")
        c.decide_approval(req["decision_id"], "approved", "admin")
        result = c.revoke_approval(req["decision_id"])
        assert result["ok"] is True
        assert result["status"] == "revoked"
        self._cleanup()

    def test_verify_approved_decision(self) -> None:
        c = self._coordinator()
        req = c.request_approval("mis-1", "proj-1", "R3", "deploy", resource="main")
        c.decide_approval(req["decision_id"], "approved", "admin")
        result = c.verify_approval(req["decision_id"], "mis-1", "proj-1", "deploy", resource="main")
        assert result["authorized"] is True
        self._cleanup()

    def test_verify_mismatch_denied(self) -> None:
        c = self._coordinator()
        req = c.request_approval("mis-1", "proj-1", "R3", "deploy")
        c.decide_approval(req["decision_id"], "approved", "admin")
        result = c.verify_approval(req["decision_id"], "mis-99", "proj-1", "deploy")
        assert result["authorized"] is False
        self._cleanup()

    def test_r4_request_approved_but_verify_denied(self) -> None:
        """P0-001: R4 approved → verify() still returns authorized=false."""
        c = self._coordinator()
        req = c.request_approval("mis-r4", "proj-1", "R4", "delete_production")
        c.decide_approval(req["decision_id"], "approved", "admin")
        result = c.verify_approval(req["decision_id"], "mis-r4", "proj-1", "delete_production")
        assert result["authorized"] is False
        assert "r4_blocked" in result["reason"]
        self._cleanup()

    def test_r4_policy_enforce_blocked(self) -> None:
        c = self._coordinator()
        req = c.request_approval("mis-r4", "proj-1", "R4", "deploy")
        c.decide_approval(req["decision_id"], "approved", "admin")
        result = c.evaluate_policy("R4", "deploy", ["deploy"], [],
                                   decision_id=req["decision_id"],
                                   mission_id="mis-r4", project_id="proj-1")
        assert result["allowed"] is False
        assert "R4_blocked" in result["reason"]
        self._cleanup()


class TestHumanControl:
    """Human control: pause, resume, cancel, takeover."""

    def _coordinator(self) -> SovereignExecutionCoordinator:
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._db_path = self._tmp.name
        return SovereignExecutionCoordinator(MockRuntime(), db_path=self._db_path)

    def _cleanup(self) -> None:
        import os
        if hasattr(self, '_db_path') and os.path.exists(self._db_path):
            os.unlink(self._db_path)

    def test_pause_mission(self) -> None:
        c = self._coordinator()
        c._runtime._missions["mis-1"] = MockMission("mis-1", "executing")
        req = ControlRequest(
            request_id="req-1", actor_id="human", mission_id="mis-1",
            project_id="nexara", trace_id="tr-1", action=ControlAction.PAUSE,
        )
        result = c.handle_control(req)
        assert result.ok is True
        assert "paused" in result.control_state
        self._cleanup()

    def test_pause_duplicate_idempotent(self) -> None:
        c = self._coordinator()
        c._runtime._missions["mis-1"] = MockMission("mis-1", "executing")
        req = ControlRequest(
            request_id="req-1", actor_id="human", mission_id="mis-1",
            project_id="nexara", trace_id="tr-1", action=ControlAction.PAUSE,
            idempotency_key="pause-key-001",
        )
        c.handle_control(req)
        result2 = c.handle_control(req)
        assert result2.ok is True
        self._cleanup()

    def test_resume_after_pause(self) -> None:
        c = self._coordinator()
        c._runtime._missions["mis-1"] = MockMission("mis-1", "paused")
        c.handle_control(ControlRequest(
            request_id="req-1", actor_id="human", mission_id="mis-1",
            project_id="nexara", trace_id="tr-1", action=ControlAction.PAUSE,
        ))
        req2 = ControlRequest(
            request_id="req-2", actor_id="human", mission_id="mis-1",
            project_id="nexara", trace_id="tr-2", action=ControlAction.RESUME,
        )
        result = c.handle_control(req2)
        assert result.ok is True
        assert result.control_state == "autonomous"
        self._cleanup()

    def test_cancel_mission(self) -> None:
        c = self._coordinator()
        c._runtime._missions["mis-1"] = MockMission("mis-1", "executing")
        req = ControlRequest(
            request_id="req-1", actor_id="human", mission_id="mis-1",
            project_id="nexara", trace_id="tr-1", action=ControlAction.CANCEL,
        )
        result = c.handle_control(req)
        assert result.ok is True
        assert result.mission_state == "cancelled"
        self._cleanup()

    def test_takeover_release_cycle(self) -> None:
        c = self._coordinator()
        c._runtime._missions["mis-1"] = MockMission("mis-1", "executing")
        r1 = c.handle_control(ControlRequest(
            request_id="r1", actor_id="human", mission_id="mis-1",
            project_id="nexara", trace_id="tr-1", action=ControlAction.TAKEOVER,
        ))
        assert r1.ok is True
        assert r1.control_state == "human_controlled"
        status = c.mission_control_status("mis-1")
        assert "release_takeover" in status["available_actions"]
        r2 = c.handle_control(ControlRequest(
            request_id="r2", actor_id="human", mission_id="mis-1",
            project_id="nexara", trace_id="tr-2", action=ControlAction.RELEASE_TAKEOVER,
        ))
        assert r2.ok is True
        assert r2.control_state == "autonomous"
        self._cleanup()

    def test_resume_fails_when_not_paused(self) -> None:
        c = self._coordinator()
        c._runtime._missions["mis-1"] = MockMission("mis-1", "executing")
        req = ControlRequest(
            request_id="req-1", actor_id="human", mission_id="mis-1",
            project_id="nexara", trace_id="tr-1", action=ControlAction.RESUME,
        )
        result = c.handle_control(req)
        assert result.ok is False
        assert "cannot_resume" in result.reason_code
        self._cleanup()

    def test_safe_mode_toggle(self) -> None:
        c = self._coordinator()
        r1 = c.handle_control(ControlRequest(
            request_id="r1", actor_id="human", mission_id="mis-1",
            project_id="nexara", trace_id="tr-1", action=ControlAction.ENABLE_SAFE_MODE,
        ))
        assert r1.ok is True
        assert r1.reason_code == "safe_mode_on"
        r2 = c.handle_control(ControlRequest(
            request_id="r2", actor_id="human", mission_id="mis-1",
            project_id="nexara", trace_id="tr-2", action=ControlAction.DISABLE_SAFE_MODE,
        ))
        assert r2.ok is True
        assert r2.reason_code == "safe_mode_off"
        self._cleanup()

    def test_mission_control_status_autonomous(self) -> None:
        c = self._coordinator()
        c._runtime._missions["mis-1"] = MockMission("mis-1", "executing")
        status = c.mission_control_status("mis-1")
        assert status["control_state"] == "autonomous"
        assert "pause" in status["available_actions"]
        assert "cancel" in status["available_actions"]
        self._cleanup()

    def test_mission_control_status_autonomous(self) -> None:
        c = self._coordinator()
        c._runtime._missions["mis-1"] = MockMission("mis-1", "executing")
        status = c.mission_control_status("mis-1")
        assert status["control_state"] == "autonomous"
        assert "pause" in status["available_actions"]
        assert "cancel" in status["available_actions"]
        self._cleanup()
