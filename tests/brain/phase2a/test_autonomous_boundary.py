"""Tests: Autonomous Improvement Boundary."""

import pytest
from src.nexara_prime.brain.evolution.boundary import (
    AutonomousBoundary, VetoRecord, ActionContext,
    AUTONOMOUS_ALLOWED, AUTONOMOUS_BLOCKED, APPROVAL_REQUIRED,
)


@pytest.fixture
def boundary():
    return AutonomousBoundary()


class TestBoundaryEnforcement:
    """15 tests: enforcement, allowed/blocked, risk, evidence."""

    def test_allowed_action_passes(self, boundary):
        result = boundary.check("memory_consolidation")
        assert result.allowed
        assert result.response == "PROCEED"

    def test_blocked_action_halted(self, boundary):
        result = boundary.check("capability_register")
        assert not result.allowed
        assert result.response == "HALT"

    def test_approval_required_without_evidence_alerted(self, boundary):
        result = boundary.check("skill_formalize")
        assert not result.allowed
        assert result.response == "ALERT_HUMAN"

    def test_approval_required_with_evidence_still_blocked(self, boundary):
        ctx = ActionContext(action_id="skill_formalize", evidence_ids=["ev1", "ev2"])
        result = boundary.check("skill_formalize", ctx)
        assert not result.allowed  # still needs human approval
        assert result.response == "ALERT_HUMAN"

    def test_risk_r3_blocked(self, boundary):
        ctx = ActionContext(action_id="memory_consolidation", risk_level="R3")
        result = boundary.check("memory_consolidation", ctx)
        assert not result.allowed
        assert "R3" in result.reason

    def test_risk_r2_allowed(self, boundary):
        ctx = ActionContext(action_id="memory_consolidation", risk_level="R2")
        result = boundary.check("memory_consolidation", ctx)
        assert result.allowed

    def test_dual_gating_capability_register_blocked(self, boundary):
        assert "capability_register" in AUTONOMOUS_BLOCKED
        assert "capability_register" not in APPROVAL_REQUIRED

    def test_dual_gating_skill_formalize_approval(self, boundary):
        assert "skill_formalize" in APPROVAL_REQUIRED
        assert "skill_formalize" not in AUTONOMOUS_BLOCKED

    def test_all_7_allowed_actions_pass(self, boundary):
        for action in AUTONOMOUS_ALLOWED:
            result = boundary.check(action)
            assert result.allowed, f"{action} should be allowed"

    def test_all_8_blocked_actions_halted(self, boundary):
        for action in AUTONOMOUS_BLOCKED:
            result = boundary.check(action)
            assert not result.allowed, f"{action} should be blocked"

    def test_is_allowed_shortcut(self, boundary):
        assert boundary.is_allowed("health_metric_compute")
        assert not boundary.is_allowed("memory_delete")

    def test_unknown_action_treated_as_allowed(self, boundary):
        """Unknown actions not in any list default to allowed (least privilege escalation)."""
        result = boundary.check("some_unknown_action")
        # Unknown actions not in blocked or approval_required lists → allowed under R1
        assert result.allowed


class TestHumanVeto:
    """10 tests: veto, revoke, persistence."""

    def test_veto_blocks_action(self, boundary):
        boundary.veto("memory_consolidation", "test veto")
        result = boundary.check("memory_consolidation")
        assert not result.allowed

    def test_revoke_restores_action(self, boundary):
        boundary.veto("memory_consolidation", "test")
        boundary.revoke_veto("memory_consolidation")
        result = boundary.check("memory_consolidation")
        assert result.allowed

    def test_get_vetoes_returns_active(self, boundary):
        boundary.veto("action_a", "reason a")
        boundary.veto("action_b", "reason b")
        vetoes = boundary.get_vetoes()
        assert len(vetoes) == 2

    def test_get_vetoes_excludes_revoked(self, boundary):
        boundary.veto("action_a", "reason")
        boundary.revoke_veto("action_a")
        assert len(boundary.get_vetoes()) == 0

    def test_has_veto_active(self, boundary):
        boundary.veto("test_action", "reason")
        assert boundary.has_veto("test_action")

    def test_has_veto_revoked(self, boundary):
        boundary.veto("test_action", "reason")
        boundary.revoke_veto("test_action")
        assert not boundary.has_veto("test_action")

    def test_veto_check_runs_first(self, boundary):
        # Veto should block even an allowed action
        boundary.veto("memory_consolidation", "veto overrides all")
        result = boundary.check("memory_consolidation")
        assert not result.allowed
        assert "veto" in result.reason.lower()

    def test_veto_record_has_source(self, boundary):
        record = boundary.veto("test", "reason", source="CLI")
        assert record.source == "CLI"

    def test_veto_record_has_reason(self, boundary):
        record = boundary.veto("test", "detailed reason here")
        assert record.reason == "detailed reason here"

    def test_revoke_nonexistent(self, boundary):
        assert not boundary.revoke_veto("nonexistent")


class TestHealthAndConfig:
    """5 tests: health, counts."""

    def test_health_returns_dict(self, boundary):
        h = boundary.health()
        assert h["component"] == "autonomous_boundary"
        assert h["allowed_actions"] == 7
        assert h["blocked_actions"] == 10  # 8 + autonomous_deploy + autonomous_release
        assert h["approval_required_actions"] == 5

    def test_health_reflects_vetoes(self, boundary):
        boundary.veto("a1", "r1")
        boundary.veto("a2", "r2")
        assert boundary.health()["active_vetoes"] == 2

    def test_boundary_decision_has_fields(self, boundary):
        result = boundary.check("memory_consolidation")
        assert result.decision_id.startswith("boundary_")
        assert result.checked_at != ""

    def test_action_context_defaults(self):
        ctx = ActionContext()
        assert ctx.risk_level == "R1"
        assert ctx.evidence_ids == []

    def test_veto_record_defaults(self):
        record = VetoRecord(action_id="test")
        assert record.veto_id.startswith("veto_")
        assert record.issued_by == "human_owner"
