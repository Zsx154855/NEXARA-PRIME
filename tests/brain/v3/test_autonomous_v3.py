"""V3 Autonomous Operating Layer tests — Mission Manager, Runtime, Environment, Scheduler, Agent Identity, Governance."""

from __future__ import annotations

import pytest

from nexara_prime.brain.mission_manager_v3 import MissionManagerV3, MissionLifecycle
from nexara_prime.brain.runtime.persistent_runtime import StateManager, RecoveryEngine, Checkpoint
from nexara_prime.models import new_id
from nexara_prime.brain.environment.intelligence import EventListener, EventType, ChangeDetector, SignalAnalyzer, EnvironmentEvent
from nexara_prime.brain.scheduler.autonomous_scheduler import MissionScheduler, TriggerType, TriggerEngine
from nexara_prime.brain.agent_identity.registry import AgentRegistry, AgentRole
from nexara_prime.brain.governance.autonomous_governance import AuthorityEngine, ApprovalOrchestrator, PolicyRuntime


# ═══ V3-A: Mission Manager (8 tests) ══════════════════════════════════════════

class TestMissionManagerV3:
    def test_create_mission(self) -> None:
        mgr = MissionManagerV3()
        m = mgr.create("Build API", "R2", priority=3)
        assert m.status == MissionLifecycle.CREATED

    def test_enqueue(self) -> None:
        mgr = MissionManagerV3()
        m = mgr.create("Task", "R1")
        q = mgr.enqueue(m.mission_id)
        assert q is not None
        assert q.status == MissionLifecycle.QUEUED

    def test_dequeue_by_priority(self) -> None:
        mgr = MissionManagerV3()
        m1 = mgr.create("Low", "R1", priority=10)
        m2 = mgr.create("High", "R1", priority=1)
        mgr.enqueue(m1.mission_id)
        mgr.enqueue(m2.mission_id)
        d = mgr.dequeue()
        assert d is not None
        assert d.priority == 1

    def test_advance_legal(self) -> None:
        mgr = MissionManagerV3()
        m = mgr.create("Task")
        mgr.enqueue(m.mission_id)
        mgr.dequeue()
        a = mgr.advance(m.mission_id, MissionLifecycle.APPROVED)
        assert a is not None

    def test_advance_illegal(self) -> None:
        mgr = MissionManagerV3()
        m = mgr.create("Task")
        a = mgr.advance(m.mission_id, MissionLifecycle.EXECUTING)
        assert a is None  # cannot skip queued/planned

    def test_pause_and_resume(self) -> None:
        mgr = MissionManagerV3()
        m = mgr.create("Task")
        mgr.enqueue(m.mission_id)
        mgr.dequeue()  # now PLANNED
        mgr.advance(m.mission_id, MissionLifecycle.APPROVED)
        mgr.advance(m.mission_id, MissionLifecycle.EXECUTING)
        mgr.pause(m.mission_id)
        r = mgr.resume(m.mission_id)
        assert r is not None
        assert r.status == MissionLifecycle.EXECUTING

    def test_list_active(self) -> None:
        mgr = MissionManagerV3()
        m = mgr.create("Active")
        mgr.enqueue(m.mission_id)
        assert len(mgr.list_active()) == 1

    def test_stats(self) -> None:
        mgr = MissionManagerV3()
        mgr.create("M1")
        mgr.create("M2")
        assert mgr.stats()["total"] == 2


# ═══ V3-A: Persistent Runtime (6 tests) ═══════════════════════════════════════

class TestPersistentRuntime:
    def test_save_and_load(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            sm = StateManager(db_path=f.name)
            cp = Checkpoint(
                checkpoint_id=new_id("cp"), mission_id="mis-1", project_id="proj-1",
                run_id=new_id("run"), trace_id=new_id("tr"), state="executing",
                step_index=3, data={"step": 3},
            )
            sm.save_checkpoint(cp)
            loaded = sm.load_checkpoint("mis-1", "proj-1")
            assert loaded is not None
            assert loaded.data["step"] == 3
            assert loaded.state == "executing"

    def test_load_nonexistent(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            assert StateManager(db_path=f.name).load_checkpoint("nope", "nope") is None

    def test_save_and_reload_new_instance(self) -> None:
        """P1: Save via process A, load via process B simulation."""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            sm1 = StateManager(db_path=db_path)
            cp = Checkpoint(
                checkpoint_id=new_id("cp"), mission_id="mis-2", project_id="proj-1",
                run_id=new_id("run"), trace_id=new_id("tr"), state="executing", step_index=5,
            )
            sm1.save_checkpoint(cp)
            sm1.close()
            del sm1
            sm2 = StateManager(db_path=db_path)
            loaded = sm2.load_checkpoint("mis-2", "proj-1")
            assert loaded is not None
            assert loaded.state == "executing"
            assert loaded.step_index == 5
            sm2.close()
        finally:
            os.unlink(db_path)

    def test_recovery_can_recover(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            sm = StateManager(db_path=f.name)
            cp = Checkpoint(new_id("cp"), "m1", "proj-1", new_id("run"), new_id("tr"), "executing", 0)
            sm.save_checkpoint(cp)
            re = RecoveryEngine(sm)
            assert re.can_recover("m1", "proj-1") is True

    def test_recovery_no_checkpoint(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            re = RecoveryEngine(StateManager(db_path=f.name))
            assert re.recover("unknown", "proj-1") is None

    def test_recovery_or_fail_raises(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            re = RecoveryEngine(StateManager(db_path=f.name))
            with pytest.raises(RuntimeError, match="recovery_failed"):
                re.recover_or_fail("unknown", "proj-1")

    def test_multiple_checkpoints(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            sm = StateManager(db_path=f.name)
            sm.save_checkpoint(Checkpoint(new_id("cp1"), "m1", "proj-1", new_id("r1"), new_id("t1"), "planning", 0))
            sm.save_checkpoint(Checkpoint(new_id("cp2"), "m1", "proj-1", new_id("r2"), new_id("t2"), "executing", 3))
            cps = sm.list_checkpoints("proj-1")
            assert len(cps) == 2
            latest = sm.load_checkpoint("m1", "proj-1")
            assert latest is not None
            assert latest.state == "executing"

    def test_idempotency_duplicate_blocked(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            sm = StateManager(db_path=f.name)
            assert sm.record_effect("proj-1", "mis-1", "write", "key-123", "hash1") is True
            assert sm.record_effect("proj-1", "mis-1", "write", "key-123", "hash1") is False
            assert sm.is_duplicate("proj-1", "mis-1", "write", "key-123") is True

    def test_idempotency_different_project_independent(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            sm = StateManager(db_path=f.name)
            assert sm.record_effect("proj-A", "mis-1", "write", "key-1", "h1") is True
            assert sm.record_effect("proj-B", "mis-1", "write", "key-1", "h1") is True

    def test_idempotency_different_mission_independent(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            sm = StateManager(db_path=f.name)
            assert sm.record_effect("proj-1", "mis-A", "write", "key-1", "h1") is True
            assert sm.record_effect("proj-1", "mis-B", "write", "key-1", "h1") is True

    def test_idempotency_different_action_independent(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            sm = StateManager(db_path=f.name)
            assert sm.record_effect("proj-1", "mis-1", "read", "key-1", "h1") is True
            assert sm.record_effect("proj-1", "mis-1", "write", "key-1", "h1") is True

    def test_checkpoint_has_trace_binding(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            sm = StateManager(db_path=f.name)
            cp = Checkpoint(new_id("cp"), "mis-1", "proj-1", "run-abc", "trace-xyz", "completed", 10)
            sm.save_checkpoint(cp)
            loaded = sm.load_checkpoint("mis-1", "proj-1")
            assert loaded is not None
            assert loaded.run_id == "run-abc"
            assert loaded.trace_id == "trace-xyz"
            assert loaded.schema_version >= 1

    def test_stats(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            sm = StateManager(db_path=f.name)
            sm.save_checkpoint(Checkpoint(new_id("cp1"), "m1", "proj-1", new_id("r1"), new_id("t1"), "s", 0))
            sm.record_effect("proj-1", "m1", "write", "k1", "h1")
            st = sm.stats()
            assert st["checkpoints"] >= 1
            assert st["idempotency_records"] >= 1

    def test_delete_checkpoint(self) -> None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            sm = StateManager(db_path=f.name)
            cp = Checkpoint(new_id("cp"), "m1", "proj-1", new_id("r1"), new_id("t1"), "done", 1)
            sm.save_checkpoint(cp)
            assert sm.delete_checkpoint(cp.checkpoint_id) is True
            assert sm.load_checkpoint("m1", "proj-1") is None


# ═══ V3-B: Environment Intelligence (6 tests) ═════════════════════════════════

class TestEnvironmentIntelligence:
    def test_event_listener(self) -> None:
        el = EventListener()
        e = el.on(EventType.TEST_FAILURE, "pytest", "3 tests failed")
        assert e.event_type == EventType.TEST_FAILURE
        assert len(el) == 1

    def test_recent_events(self) -> None:
        el = EventListener()
        for i in range(5):
            el.on(EventType.FILE_CHANGE, f"file_{i}", f"changed {i}")
        assert len(el.recent(3)) == 3

    def test_change_detector(self) -> None:
        cd = ChangeDetector()
        events = [EnvironmentEvent("e1", EventType.TEST_FAILURE, "src", "test1"),
                   EnvironmentEvent("e2", EventType.TEST_FAILURE, "src", "test2"),
                   EnvironmentEvent("e3", EventType.TEST_FAILURE, "src", "test3")]
        changes = cd.detect(events)
        assert len(changes) >= 1
        assert changes[0]["action"] == "create_recovery_mission"

    def test_change_detector_file_changes(self) -> None:
        cd = ChangeDetector()
        events = [EnvironmentEvent(f"e{i}", EventType.FILE_CHANGE, "src", "change") for i in range(6)]
        changes = cd.detect(events)
        assert any(c["action"] == "create_audit_mission" for c in changes)

    def test_signal_analyzer_test_failures(self) -> None:
        sa = SignalAnalyzer()
        events = [EnvironmentEvent("e1", EventType.TEST_FAILURE, "src", "fail"),
                   EnvironmentEvent("e2", EventType.TEST_FAILURE, "src", "fail")]
        proposals = sa.analyze(events)
        assert len(proposals) >= 1
        assert proposals[0]["mission"] == "fix_failing_tests"

    def test_signal_analyzer_file_changes(self) -> None:
        sa = SignalAnalyzer()
        events = [EnvironmentEvent(f"e{i}", EventType.FILE_CHANGE, "src", "change") for i in range(6)]
        proposals = sa.analyze(events)
        assert any(p["mission"] == "audit_recent_changes" for p in proposals)


# ═══ V3-C: Autonomous Scheduler (6 tests) ═════════════════════════════════════

class TestAutonomousScheduler:
    def test_schedule(self) -> None:
        ms = MissionScheduler()
        s = ms.schedule("Daily health check", TriggerType.PERIODIC, "every_24h")
        assert s.enabled is True

    def test_trigger(self) -> None:
        ms = MissionScheduler()
        s = ms.schedule("Backup", TriggerType.TIME, "0 3 * * *")
        t = ms.trigger(s.schedule_id)
        assert t is not None
        assert t.last_triggered != ""

    def test_disable(self) -> None:
        ms = MissionScheduler()
        s = ms.schedule("Task", TriggerType.TIME, "daily")
        ms.disable(s.schedule_id)
        assert ms.list_enabled() == []

    def test_trigger_condition_true(self) -> None:
        ms = MissionScheduler()
        ms.schedule("Fix tests", TriggerType.CONDITION, "test_failure")
        te = TriggerEngine(ms)
        triggered = te.check_and_trigger("test_failure", {"test_status": "failed"})
        assert len(triggered) == 1

    def test_trigger_condition_false(self) -> None:
        ms = MissionScheduler()
        ms.schedule("Fix tests", TriggerType.CONDITION, "test_failure")
        te = TriggerEngine(ms)
        triggered = te.check_and_trigger("test_failure", {"test_status": "passing"})
        assert len(triggered) == 0

    def test_scheduler_stats(self) -> None:
        ms = MissionScheduler()
        ms.schedule("A", TriggerType.TIME, "daily")
        ms.schedule("B", TriggerType.PERIODIC, "hourly")
        assert ms.stats()["total_schedules"] == 2


# ═══ V3-D: Agent Identity (6 tests) ═══════════════════════════════════════════

class TestAgentIdentity:
    def test_register(self) -> None:
        reg = AgentRegistry()
        a = reg.register(AgentRole.ARCHITECT)
        assert a.role == AgentRole.ARCHITECT

    def test_can_execute_allowed(self) -> None:
        reg = AgentRegistry()
        a = reg.register(AgentRole.EXECUTOR)
        assert reg.can_execute(a.agent_id, "implementation", "R2") is True

    def test_can_execute_forbidden(self) -> None:
        reg = AgentRegistry()
        a = reg.register(AgentRole.EXECUTOR)
        assert reg.can_execute(a.agent_id, "governance_change", "R1") is False

    def test_can_execute_risk_too_high(self) -> None:
        reg = AgentRegistry()
        a = reg.register(AgentRole.EXECUTOR)
        assert reg.can_execute(a.agent_id, "implementation", "R4") is False

    def test_architect_cannot_execute(self) -> None:
        reg = AgentRegistry()
        a = reg.register(AgentRole.ARCHITECT)
        assert reg.can_execute(a.agent_id, "direct_execution", "R1") is False

    def test_record_mission_reputation(self) -> None:
        reg = AgentRegistry()
        a = reg.register(AgentRole.EXECUTOR)
        reg.record_mission(a.agent_id, True)
        reg.record_mission(a.agent_id, True)
        reg.record_mission(a.agent_id, False)
        agent = reg.get(a.agent_id)
        assert agent is not None
        assert agent.reputation > 0.5


# ═══ V3-E: Autonomous Governance (6 tests) ════════════════════════════════════

class TestAutonomousGovernance:
    def test_authority_r0_auto(self) -> None:
        ae = AuthorityEngine()
        result = ae.authorize("R0", "executor", "read_file")
        assert result["approval_level"] == "auto"
        assert result["authorized"] is True
        assert result["can_execute"] is True

    def test_authority_r1_auto(self) -> None:
        ae = AuthorityEngine()
        result = ae.authorize("R1", "executor", "run_tests")
        assert result["authorized"] is True

    def test_authority_r2_fail_closed(self) -> None:
        """P0: R2 requires approved decision — default is unauthorized."""
        ae = AuthorityEngine()
        result = ae.authorize("R2", "executor", "modify_config")
        assert result["authorized"] is False
        assert result["can_plan"] is True
        assert result["can_execute"] is False

    def test_authority_r3_fail_closed(self) -> None:
        """P0: R3 requires human approval — default is unauthorized."""
        ae = AuthorityEngine()
        result = ae.authorize("R3", "executor", "deploy")
        assert result["authorized"] is False
        assert result["requires_human"] is True
        assert result["can_execute"] is False

    def test_authority_r4_blocked(self) -> None:
        ae = AuthorityEngine()
        result = ae.authorize("R4", "executor", "delete_production")
        assert result["authorized"] is False
        assert result["can_plan"] is False
        assert result["can_execute"] is False

    def test_approval_request_pending_not_authorized(self) -> None:
        """P0: request() creates PENDING — verify() denies authorization."""
        ao = ApprovalOrchestrator()
        d = ao.request("mis-1", "proj-1", "R3", "deploy", resource="main")
        assert d.status == "pending"
        # Authorization must come from verify(), not d.authorized (field removed)
        result = ao.verify(d.decision_id, mission_id="mis-1", project_id="proj-1", action="deploy")
        assert result["authorized"] is False  # not APPROVED yet

    def test_approval_request_and_approve(self) -> None:
        ao = ApprovalOrchestrator()
        d = ao.request("mis-1", "proj-1", "R3", "deploy", resource="main")
        a = ao.approve(d.decision_id, "admin")
        assert a is not None
        assert a.status == "approved"
        # Authorization from verify(), NOT from a.authorized (field removed)
        result = ao.verify(d.decision_id, mission_id="mis-1", project_id="proj-1", action="deploy", resource="main")
        assert result["authorized"] is True

    def test_approval_reject(self) -> None:
        ao = ApprovalOrchestrator()
        d = ao.request("mis-1", "proj-1", "R2", "modify", resource="config")
        r = ao.reject(d.decision_id, "too risky")
        assert r is not None
        assert r.status == "rejected"
        result = ao.verify(d.decision_id, mission_id="mis-1", project_id="proj-1", action="modify")
        assert result["authorized"] is False

    def test_approval_revoked(self) -> None:
        ao = ApprovalOrchestrator()
        d = ao.request("mis-1", "proj-1", "R3", "deploy", resource="main")
        ao.approve(d.decision_id, "admin")
        rv = ao.revoke(d.decision_id)
        assert rv is not None
        result = ao.verify(d.decision_id, mission_id="mis-1", project_id="proj-1", action="deploy")
        assert result["authorized"] is False

    def test_verify_mission_mismatch(self) -> None:
        """P0: verify fails when mission_id doesn't match."""
        ao = ApprovalOrchestrator()
        d = ao.request("mis-A", "proj-1", "R3", "deploy")
        ao.approve(d.decision_id, "admin")
        result = ao.verify(d.decision_id, mission_id="mis-B", project_id="proj-1", action="deploy")
        assert result["authorized"] is False
        assert "mission_id_mismatch" in result["reason"]

    def test_verify_project_mismatch(self) -> None:
        """P0: verify fails when project_id doesn't match."""
        ao = ApprovalOrchestrator()
        d = ao.request("mis-1", "proj-A", "R3", "deploy")
        ao.approve(d.decision_id, "admin")
        result = ao.verify(d.decision_id, mission_id="mis-1", project_id="proj-B", action="deploy")
        assert result["authorized"] is False

    def test_verify_action_mismatch(self) -> None:
        """P0: verify fails when action doesn't match."""
        ao = ApprovalOrchestrator()
        d = ao.request("mis-1", "proj-1", "R3", "deploy")
        ao.approve(d.decision_id, "admin")
        result = ao.verify(d.decision_id, mission_id="mis-1", project_id="proj-1", action="delete")
        assert result["authorized"] is False

    def test_verify_consumed_replay_blocked(self) -> None:
        """P0: consumed decision cannot be replayed."""
        ao = ApprovalOrchestrator()
        d = ao.request("mis-1", "proj-1", "R3", "deploy")
        ao.approve(d.decision_id, "admin")
        ao.consume(d.decision_id)
        result = ao.verify(d.decision_id, mission_id="mis-1", project_id="proj-1", action="deploy")
        assert result["authorized"] is False

    def test_verify_nonexistent_decision(self) -> None:
        """P0: nonexistent decision is not authorized."""
        ao = ApprovalOrchestrator()
        result = ao.verify("nonexistent", mission_id="mis-1", project_id="proj-1", action="deploy")
        assert result["authorized"] is False

    def test_policy_r0_allowed(self) -> None:
        pr = PolicyRuntime()
        result = pr.enforce("R0", "read_file", ["read_file", "write_file"], ["deploy"])
        assert result["allowed"] is True

    def test_policy_r2_blocked_without_decision(self) -> None:
        """P0: R2 requires decision_id — blocked without it."""
        pr = PolicyRuntime()
        result = pr.enforce("R2", "modify", ["modify"], [])
        assert result["allowed"] is False
        assert "missing_decision_id" in result["reason"]

    def test_policy_r3_blocked_without_decision(self) -> None:
        """P0: R3 requires decision_id — blocked without it."""
        pr = PolicyRuntime()
        result = pr.enforce("R3", "deploy", ["deploy"], [])
        assert result["allowed"] is False

    def test_policy_r3_allowed_with_valid_decision(self) -> None:
        """P0: R3 with valid approved decision is allowed."""
        ao = ApprovalOrchestrator()
        pr = PolicyRuntime()
        pr.bind_orchestrator(ao)
        d = ao.request("mis-1", "proj-1", "R3", "deploy")
        ao.approve(d.decision_id, "admin")
        result = pr.enforce("R3", "deploy", ["deploy"], [], decision_id=d.decision_id,
                           mission_id="mis-1", project_id="proj-1")
        assert result["allowed"] is True

    def test_policy_r1_forbidden(self) -> None:
        pr = PolicyRuntime()
        result = pr.enforce("R1", "deploy", ["read_file"], ["deploy"])
        assert result["allowed"] is False

    def test_policy_r4_blocked(self) -> None:
        pr = PolicyRuntime()
        result = pr.enforce("R4", "anything", ["anything"], [])
        assert result["allowed"] is False
        assert "R4_blocked" in result["reason"]

    # ═══ P0-001 Regression Tests (approve does NOT authorize) ═══════════════

    def test_r4_without_approval_fail_closed(self) -> None:
        """P0 regression: R4 mission without approved decision — all denied."""
        ae = AuthorityEngine()
        result = ae.authorize("R4", "executor", "delete_production")
        assert result["authorized"] is False
        assert result["can_execute"] is False
        assert result["can_plan"] is False

        pr = PolicyRuntime()
        r = pr.enforce("R4", "delete_production", ["delete_production"], [])
        assert r["allowed"] is False

    def test_approval_does_not_bypass_policy(self) -> None:
        """P0 regression: approve() records status only — does NOT authorize.
        Authorization requires verify() or PolicyRuntime.enforce()."""
        ao = ApprovalOrchestrator()
        d = ao.request("mis-1", "proj-1", "R3", "deploy", resource="main")
        approved = ao.approve(d.decision_id, "admin")
        assert approved is not None
        assert approved.status == "approved"
        # KEY: approve() does NOT have authorized field anymore
        assert not hasattr(approved, "authorized"), \
            "P0 FAIL: approval should not carry authorization — field must not exist"
        # Authorization only from verify():
        result = ao.verify(d.decision_id, mission_id="mis-1", project_id="proj-1",
                          action="deploy", resource="main")
        assert result["authorized"] is True

    def test_authorization_requires_policy_evaluation(self) -> None:
        """P0 regression: no Policy Decision → execution blocked.
        Even with an APPROVED decision, enforce() is the gate."""
        ao = ApprovalOrchestrator()
        pr = PolicyRuntime()
        pr.bind_orchestrator(ao)
        d = ao.request("mis-2", "proj-2", "R3", "deploy")
        ao.approve(d.decision_id, "admin")
        # Without passing decision_id → blocked
        r = pr.enforce("R3", "deploy", ["deploy"], [], mission_id="mis-2", project_id="proj-2")
        assert r["allowed"] is False
        assert "missing_decision_id" in r["reason"]
        # With decision_id → allowed (policy evaluation passed)
        r2 = pr.enforce("R3", "deploy", ["deploy"], [], decision_id=d.decision_id,
                       mission_id="mis-2", project_id="proj-2")
        assert r2["allowed"] is True

    def test_approval_replay_cannot_escalate(self) -> None:
        """P0 regression: old approval record cannot authorize a new mission.
        Replay blocked by mission_id mismatch in verify()."""
        ao = ApprovalOrchestrator()
        d = ao.request("mis-old", "proj-1", "R3", "deploy")
        ao.approve(d.decision_id, "admin")
        # Try to use old approval for new mission
        result = ao.verify(d.decision_id, mission_id="mis-new", project_id="proj-1",
                          action="deploy")
        assert result["authorized"] is False
        assert "mission_id_mismatch" in result["reason"]
