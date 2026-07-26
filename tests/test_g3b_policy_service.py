"""G3-B: PolicyService Contract Tests."""
from __future__ import annotations

import pytest

from nexara_prime.events import EventBus
from nexara_prime.governance import ApprovalEngine, PolicyEngine, WriterLeaseManager
from nexara_prime.models import RiskLevel
from nexara_prime.policy_service import PolicyService, PolicyServiceHealth


class FakeStore:
    def execute(self, *a, **kw): return None
    def executemany(self, *a, **kw): pass
    def fetchone(self, *a, **kw): return None
    def fetchall(self, *a, **kw): return []
    def list_records(self, *a, **kw): return []
    def list_record_envelopes(self, *a, **kw): return []
    def commit(self, *a, **kw): pass
    def close(self, *a, **kw): pass


class TestPolicyServiceLifecycle:
    """Service lifecycle: start → health → stop."""

    @pytest.fixture
    def service(self) -> PolicyService:
        store = FakeStore()
        events = EventBus(store)  # type: ignore[arg-type]
        return PolicyService(store, events)

    def test_service_starts_and_stops(self, service: PolicyService) -> None:
        assert not service.running
        service.start()
        assert service.running
        service.stop()
        assert not service.running

    def test_health_reflects_running_state(self, service: PolicyService) -> None:
        service.start()
        h = service.health()
        assert isinstance(h, PolicyServiceHealth)
        assert h.status == "healthy"
        assert h.policy_engine
        assert h.approval_engine
        assert h.lease_manager

    def test_health_shows_stopped_when_not_started(self, service: PolicyService) -> None:
        h = service.health()
        assert h.status == "stopped"


class TestPolicyDelegation:
    """PolicyService delegates correctly to wrapped engines."""

    @pytest.fixture
    def service(self) -> PolicyService:
        return PolicyService(FakeStore(), EventBus(FakeStore()))  # type: ignore[arg-type]

    def test_policy_engine_wrapped_unchanged(self, service: PolicyService) -> None:
        """PolicyService wraps PolicyEngine — does not replace it."""
        assert isinstance(service.policy, PolicyEngine)

    def test_approval_engine_wrapped_unchanged(self, service: PolicyService) -> None:
        assert isinstance(service.approvals, ApprovalEngine)

    def test_lease_manager_wrapped_unchanged(self, service: PolicyService) -> None:
        assert isinstance(service.leases, WriterLeaseManager)

    def test_requires_approval_delegates(self, service: PolicyService) -> None:
        assert service.requires_approval(RiskLevel.R2)
        assert not service.requires_approval(RiskLevel.R0)
        assert not service.requires_approval(RiskLevel.R1)

    def test_allows_tool_delegates(self, service: PolicyService) -> None:
        ok, reason = service.allows_tool("file_read", RiskLevel.R0)
        assert ok, f"file_read should be allowed, got: {reason}"

    def test_r4_actions_blocked(self, service: PolicyService) -> None:
        ok, reason = service.allows_tool("any_tool", RiskLevel.R4)
        assert not ok, f"R4 actions must be blocked, got: {reason}"
        assert "R4" in reason

    def test_safe_mode_restricts_tools(self, service: PolicyService) -> None:
        ok, reason = service.allows_tool("file_read", RiskLevel.R1, safe_mode=True)
        assert ok, f"file_read should be allowed in safe_mode, got: {reason}"
        ok2, _ = service.allows_tool("code_exec", RiskLevel.R1, safe_mode=True)
        assert not ok2, "code_exec must be blocked in safe_mode"


class TestGovernanceModuleUntouched:
    """G3-B constraint: governance.py must NOT be modified."""

    def test_governance_py_unchanged(self) -> None:
        """Verify governance.py still exports original classes."""
        from nexara_prime import governance
        assert hasattr(governance, "PolicyEngine")
        assert hasattr(governance, "ApprovalEngine")
        assert hasattr(governance, "WriterLeaseManager")

    def test_policy_service_imports_from_governance(self) -> None:
        """PolicyService imports from governance, not reimplements."""
        source = (__import__('pathlib').Path(__file__).parent.parent /
                  "src/nexara_prime/policy_service.py").read_text()
        assert "from .governance import" in source
        assert "class PolicyEngine" not in source  # Not reimplemented
        assert "class ApprovalEngine" not in source
        assert "class WriterLeaseManager" not in source
