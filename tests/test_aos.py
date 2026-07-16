"""Tests for NEXARA Autonomous Operating System — execution gateway and supervisor."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.aos.command_classifier import (
    CommandClassifier, RiskLevel,
)
from nexara_prime.aos.permission_broker import PermissionBroker
from nexara_prime.aos.recovery_engine import RecoveryEngine, RecoveryStrategy
from nexara_prime.aos.policy_engine import PolicyEngine, PolicyDecision
from nexara_prime.aos.cost_optimizer import CostOptimizer, TokenUsage
from nexara_prime.aos.context_compactor import ContextCompactor, CompactionStrategy
from nexara_prime.aos.health_monitor import HealthMonitor, WorkerStatus
from nexara_prime.aos.notification_gateway import (
    NotificationGateway, NotificationLevel,
)
from nexara_prime.aos.execution_gateway import ExecutionGateway
from nexara_prime.aos.supervisor import AutonomousSupervisor


# ── fixtures ──

@pytest.fixture
def tmp_db():
    d = tempfile.mkdtemp(prefix="nexara_aos_test_")
    store = SQLiteStore(Path(d) / "test.db")
    yield store
    store.close()
    import shutil
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def events(tmp_db):
    return EventBus(tmp_db)


@pytest.fixture
def evidence(tmp_db, events):
    return EvidenceStore(tmp_db, events)


@pytest.fixture
def classifier():
    return CommandClassifier()


@pytest.fixture
def broker():
    return PermissionBroker()


@pytest.fixture
def recovery():
    return RecoveryEngine(max_retries=3)


@pytest.fixture
def policy():
    return PolicyEngine()


@pytest.fixture
def cost():
    return CostOptimizer()


@pytest.fixture
def compactor():
    return ContextCompactor()


@pytest.fixture
def health():
    return HealthMonitor()


@pytest.fixture
def notifications():
    return NotificationGateway()


@pytest.fixture
def gateway():
    return ExecutionGateway()


@pytest.fixture
def supervisor(tmp_db, events, evidence):
    return AutonomousSupervisor(tmp_db, events, evidence)


# ── Command Classifier tests ──

class TestCommandClassifier:
    def test_read_command_r0(self, classifier):
        c = classifier.classify("ls -la")
        assert c.risk_level == RiskLevel.R0
        assert c.auto_approvable

    def test_git_status_r0(self, classifier):
        c = classifier.classify("git status --short")
        assert c.risk_level == RiskLevel.R0
        assert c.auto_approvable

    def test_pytest_r1(self, classifier):
        c = classifier.classify("python -m pytest tests/ -q")
        assert c.risk_level == RiskLevel.R1
        assert c.auto_approvable

    def test_write_file_r2(self, classifier):
        c = classifier.classify("Write /tmp/test.py")
        assert c.risk_level == RiskLevel.R2
        assert c.auto_approvable

    def test_git_push_r3(self, classifier):
        c = classifier.classify("git push origin work/test")
        assert c.risk_level == RiskLevel.R3
        assert not c.auto_approvable

    def test_rm_rf_r4(self, classifier):
        c = classifier.classify("rm -rf /important")
        assert c.risk_level == RiskLevel.R4
        assert not c.auto_approvable

    def test_sudo_r4(self, classifier):
        c = classifier.classify("sudo something")
        assert c.risk_level == RiskLevel.R4

    def test_gh_api_read_r0(self, classifier):
        c = classifier.classify("gh api repos/Zsx154855/NEXARA-PRIME")
        assert c.risk_level == RiskLevel.R0

    def test_gh_pr_merge_r4(self, classifier):
        c = classifier.classify("gh pr merge 8")
        assert c.risk_level == RiskLevel.R4
        assert not c.auto_approvable

    def test_git_tag_r4(self, classifier):
        c = classifier.classify("git tag v0.1.0")
        assert c.risk_level == RiskLevel.R4


# ── Permission Broker tests ──

class TestPermissionBroker:
    def test_r0_auto_approved(self, broker):
        d = broker.evaluate("git status", mission_id="m1", worker_id="w1")
        assert d.decision == "auto_approved"
        assert d.risk_level == RiskLevel.R0

    def test_r1_auto_approved(self, broker):
        d = broker.evaluate("pytest tests/ -q", mission_id="m1", worker_id="w1")
        assert d.decision == "auto_approved"

    def test_r2_auto_approved(self, broker):
        d = broker.evaluate("Write /tmp/ok.py", mission_id="m1", worker_id="w1")
        assert d.decision == "auto_approved"

    def test_r4_escalated(self, broker):
        d = broker.evaluate("rm -rf /", mission_id="m1", worker_id="w1")
        assert d.decision == "escalated"

    def test_counts(self, broker):
        broker.evaluate("ls", mission_id="m1", worker_id="w1")
        broker.evaluate("sudo rm", mission_id="m2", worker_id="w2")
        assert broker.auto_approved_count == 1
        assert broker.escalated_count == 1


# ── Recovery Engine tests ──

class TestRecoveryEngine:
    def test_retry_on_first_attempt(self, recovery):
        result = recovery.recover("m1", "test_failure", attempt=1, last_error="oops")
        assert result.strategy == RecoveryStrategy.RETRY
        assert result.success

    def test_escalate_after_max(self, recovery):
        result = recovery.recover("m1", "test_failure", attempt=8)
        assert result.strategy == RecoveryStrategy.ESCALATE

    def test_circuit_breaker(self, recovery):
        for _ in range(6):
            recovery.recover("m2", "circuit_test", attempt=1)
        assert recovery.is_circuit_open("m2", "circuit_test")

    def test_reset(self, recovery):
        recovery.recover("m3", "reset_test", attempt=1)
        recovery.reset("m3", "reset_test")
        assert not recovery.is_circuit_open("m3", "reset_test")


# ── Policy Engine tests ──

class TestPolicyEngine:
    def test_read_allowed(self, policy):
        assert policy.evaluate("git status", RiskLevel.R0) == PolicyDecision.ALLOW

    def test_test_run_allowed(self, policy):
        assert policy.evaluate("pytest tests/", RiskLevel.R1) == PolicyDecision.ALLOW

    def test_write_allowed(self, policy):
        assert policy.evaluate("Write /tmp/x.py", RiskLevel.R2) == PolicyDecision.ALLOW

    def test_sudo_denied(self, policy):
        assert policy.evaluate("sudo rm", RiskLevel.R4) == PolicyDecision.DENY

    def test_merge_asks_human(self, policy):
        assert policy.evaluate("gh pr merge 5", RiskLevel.R4) == PolicyDecision.ASK_HUMAN


# ── Cost Optimizer tests ──

class TestCostOptimizer:
    def test_initial_budget(self, cost):
        assert cost.budget.maximum_budget == 350000
        assert cost.remaining() == 350000

    def test_record_usage(self, cost):
        cost.record(TokenUsage(tokens_in=5000, tokens_out=3000, mission_id="m1"))
        assert cost.remaining() == 350000 - 8000

    def test_over_budget(self, cost):
        cost.record(TokenUsage(tokens_in=350000, tokens_out=0, mission_id="m1"))
        assert cost.is_over_budget()

    def test_recommend_model(self, cost):
        model = cost.recommend_model("planning")
        assert model in ("sonnet", "haiku")

    def test_compaction_strategy(self, cost):
        s = cost.compaction_strategy()
        assert s in ("none", "moderate", "aggressive")


# ── Context Compactor tests ──

class TestContextCompactor:
    def test_first_read_always_allowed(self, compactor):
        assert compactor.should_read("file_a.py")

    def test_re_read_blocked_aggressive(self, compactor):
        compactor.strategy = CompactionStrategy.AGGRESSIVE
        compactor.mark_read("file_a.py")
        assert not compactor.should_read("file_a.py")

    def test_re_read_allowed_moderate(self, compactor):
        compactor.strategy = CompactionStrategy.MODERATE
        compactor.mark_read("file_a.py")
        assert compactor.should_read("file_a.py")  # once more
        compactor.mark_read("file_a.py")
        assert not compactor.should_read("file_a.py")  # third read blocked


# ── Health Monitor tests ──

class TestHealthMonitor:
    def test_register_and_heartbeat(self, health):
        health.register("w1")
        h = health.heartbeat("w1")
        assert h.status == WorkerStatus.HEALTHY

    def test_unresponsive_detection(self, health):
        h = health.register("w2")
        h.last_heartbeat = 0  # force old heartbeat
        health.check_all()
        assert health.get("w2").status == WorkerStatus.DEAD

    def test_error_degradation(self, health):
        health.register("w3")
        for _ in range(3):
            health.record_error("w3", "test error")
        assert health.get("w3").status == WorkerStatus.DEGRADED

    def test_alive_workers(self, health):
        health.register("w1")
        health.heartbeat("w1")
        health.register("w2")
        health.heartbeat("w2")
        health.register("w3")
        h = health.get("w3")
        if h:
            h.last_heartbeat = 0
        alive = health.get_alive_workers()
        assert len(alive) == 2


# ── Notification Gateway tests ──

class TestNotificationGateway:
    def test_info_not_user_facing(self, notifications):
        assert not notifications.should_interrupt_user(NotificationLevel.INFO)

    def test_approval_is_user_facing(self, notifications):
        assert notifications.should_interrupt_user(NotificationLevel.APPROVAL_REQUIRED)

    def test_critical_is_user_facing(self, notifications):
        assert notifications.should_interrupt_user(NotificationLevel.CRITICAL)

    def test_success_not_user_facing(self, notifications):
        n = notifications.notify(NotificationLevel.SUCCESS, "Done", "Mission complete")
        assert n.delivered is False  # no channels registered


# ── Execution Gateway tests ──

class TestExecutionGateway:
    def test_register_and_list(self, gateway):
        class FakeWorker:
            worker_id = "fake_1"
            worker_type = type("WT", (), {"value": "local_tool"})()
            def is_alive(self): return True
            def execute(self, *a, **kw): return None
            def resume(self, *a): return None
            def health(self): return {}

        gateway.register(FakeWorker())
        workers = gateway.list_workers()
        assert len(workers) == 1
        assert workers[0]["worker_id"] == "fake_1"


# ── Supervisor tests ──

class TestSupervisor:
    def test_submit_and_query_mission(self, supervisor):
        item = supervisor.submit_mission("mission_x", priority=5)
        assert item.mission_id == "mission_x"
        status = supervisor.mission_status("mission_x")
        assert status["state"] in ("queued", "ready")

    def test_not_found(self, supervisor):
        status = supervisor.mission_status("nonexistent")
        assert status["status"] == "not_found"

    def test_status_report(self, supervisor):
        report = supervisor.status_report()
        assert "supervisor_state" in report
        assert "orchestrator" in report
        assert "permissions" in report
        assert "recovery" in report

    def test_start_stop(self, supervisor):
        supervisor.start(block=False)
        time.sleep(0.1)
        assert supervisor.state.value in ("idle", "planning", "monitoring")
        supervisor.stop()
