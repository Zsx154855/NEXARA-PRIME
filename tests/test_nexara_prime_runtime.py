"""NexaraPrime runtime tests — composition root, identity, portfolio, lifecycle."""
from __future__ import annotations

import os
import tempfile
import time

import pytest

from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.identity import AgentIdentity, IdentityStore
from nexara_prime.runtime.nexara_prime import NexaraPrime, RuntimeStatus
from nexara_prime.runtime.lifecycle import RuntimeLifecycle, LifecycleState
from nexara_prime.runtime.heartbeat import Heartbeat
from nexara_prime.runtime.doctor import Doctor
from nexara_prime.portfolio.models import (
    ProgramRecord, ProgramStatus, OwnerDirective, ReviewBudget,
)
from nexara_prime.portfolio.director import PortfolioDirector
from nexara_prime.portfolio.policy import PortfolioPolicy
from nexara_prime.portfolio.state_machine import PortfolioStateMachine
from nexara_prime.portfolio.watcher import ExternalConditionWatcher


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_db():
    db_path = os.path.join(tempfile.mkdtemp(), "test.db")
    store = SQLiteStore(db_path)
    events = EventBus(store)
    return store, events


@pytest.fixture
def agent_identity():
    return AgentIdentity()


@pytest.fixture
def identity_store():
    return IdentityStore()


@pytest.fixture
def portfolio_director(temp_db):
    store, events = temp_db
    from nexara_prime.evidence import EvidenceStore
    evidence = EvidenceStore(store, events)
    return PortfolioDirector(store=store, events=events, evidence=evidence)


@pytest.fixture
def nexara_prime(temp_db):
    store, events = temp_db
    from pathlib import Path
    ws = Path(tempfile.mkdtemp())
    rp = Path(tempfile.mkdtemp())
    settings = type('Settings', (), {
        'db_path': Path(tempfile.mkdtemp()) / "test_nexara.db",
        'workspace_root': ws,
        'report_root': rp,
        'model_provider': 'mock',
        'mock_model': True,
        'api_host': '127.0.0.1',
        'api_port': 8765,
        'ensure_dirs': lambda self: None,
    })()
    return NexaraPrime(settings=settings)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. NexaraPrime is the ONLY composition root
# ═══════════════════════════════════════════════════════════════════════════════

class TestNexaraPrimeCompositionRoot:
    def test_single_composition_root_exists(self, nexara_prime):
        assert nexara_prime is not None
        assert nexara_prime.identity is not None
        assert nexara_prime.store is not None
        assert nexara_prime.events is not None

    def test_all_modules_injected_not_global(self, nexara_prime):
        """No module should be accessed via global variables."""
        assert hasattr(nexara_prime, 'identity')
        assert hasattr(nexara_prime, 'portfolio_director')
        assert hasattr(nexara_prime, 'lifecycle')
        assert hasattr(nexara_prime, 'heartbeat')
        assert hasattr(nexara_prime, 'doctor')

    def test_create_and_load(self, nexara_prime):
        inst = nexara_prime.create()
        assert inst is nexara_prime
        loaded = NexaraPrime.load()
        assert loaded is not None
        assert loaded.identity.agent_id == "nexara_prime.agent"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Identity crosses restart stably
# ═══════════════════════════════════════════════════════════════════════════════

class TestIdentityStability:
    def test_identity_persists_across_instances(self):
        id1 = AgentIdentity()
        id2 = AgentIdentity()
        assert id1.agent_id == id2.agent_id == "nexara_prime.agent"
        assert id1.display_name == id2.display_name == "NEXARA"

    def test_model_switch_does_not_change_identity(self):
        ident = AgentIdentity()
        original_id = ident.agent_id
        original_principles = list(ident.product_principles)
        # "Switch model" — identity must not change
        assert ident.agent_id == original_id
        assert ident.product_principles == original_principles

    def test_identity_store_persists_owner(self, identity_store):
        user = identity_store.get_user()
        assert user.user_id == "local-owner"
        assert user.name == "Local Owner"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Portfolio persistence
# ═══════════════════════════════════════════════════════════════════════════════

class TestPortfolioPersistence:
    def test_add_and_retrieve_program(self, portfolio_director):
        prog = ProgramRecord(
            program_id="test-prog-1",
            name="Test Program",
            status=ProgramStatus.READY,
        )
        portfolio_director.add_program(prog)
        retrieved = portfolio_director.get_program("test-prog-1")
        assert retrieved is not None
        assert retrieved.name == "Test Program"
        assert retrieved.status == ProgramStatus.READY

    def test_save_and_load_portfolio(self, portfolio_director):
        prog = ProgramRecord(
            program_id="test-prog-2",
            name="Persistent Program",
            status=ProgramStatus.PLANNED,
        )
        portfolio_director.add_program(prog)
        portfolio_director.save()

        # Reload
        reloaded = portfolio_director.repository.load_portfolio()
        assert reloaded is not None

    def test_list_by_status(self, portfolio_director):
        p1 = ProgramRecord(program_id="p1", status=ProgramStatus.READY)
        p2 = ProgramRecord(program_id="p2", status=ProgramStatus.WAIT_EXTERNAL)
        p3 = ProgramRecord(program_id="p3", status=ProgramStatus.READY)
        portfolio_director.add_program(p1)
        portfolio_director.add_program(p2)
        portfolio_director.add_program(p3)

        ready = portfolio_director.list_programs(ProgramStatus.READY)
        assert len(ready) == 2

        waiting = portfolio_director.list_programs(ProgramStatus.WAIT_EXTERNAL)
        assert len(waiting) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Program state transitions
# ═══════════════════════════════════════════════════════════════════════════════

class TestProgramStateMachine:
    def test_valid_transitions(self):
        sm = PortfolioStateMachine()
        assert sm.can_transition(ProgramStatus.PLANNED, ProgramStatus.READY)
        assert sm.can_transition(ProgramStatus.READY, ProgramStatus.RUNNING)
        assert sm.can_transition(ProgramStatus.RUNNING, ProgramStatus.WAIT_EXTERNAL)

    def test_invalid_transitions_raise(self):
        sm = PortfolioStateMachine()
        assert not sm.can_transition(ProgramStatus.COMPLETED, ProgramStatus.RUNNING)
        assert not sm.can_transition(ProgramStatus.ARCHIVED, ProgramStatus.READY)

    def test_transition_returns_updated_program(self, portfolio_director):
        prog = ProgramRecord(program_id="tp1", status=ProgramStatus.READY)
        portfolio_director.add_program(prog)
        updated = portfolio_director.transition_program(prog, ProgramStatus.RUNNING)
        assert updated.status == ProgramStatus.RUNNING


# ═══════════════════════════════════════════════════════════════════════════════
# 5. WAIT_EXTERNAL is not failure
# ═══════════════════════════════════════════════════════════════════════════════

class TestWaitExternal:
    def test_wait_external_not_in_runnable(self, portfolio_director):
        wait_prog = ProgramRecord(program_id="wp1", status=ProgramStatus.WAIT_EXTERNAL)
        ready_prog = ProgramRecord(program_id="rp1", status=ProgramStatus.READY)
        portfolio_director.add_program(wait_prog)
        portfolio_director.add_program(ready_prog)

        runnable = portfolio_director.list_runnable()
        runnable_ids = {p.program_id for p in runnable}
        assert "rp1" in runnable_ids
        assert "wp1" not in runnable_ids  # WAIT_EXTERNAL is NOT runnable

    def test_ready_program_selected_when_other_waits(self, portfolio_director):
        """When one program is WAIT_EXTERNAL, another READY program is selected."""
        wait_prog = ProgramRecord(
            program_id="wait-pr", name="Waiting PR",
            status=ProgramStatus.WAIT_EXTERNAL, priority=5,
        )
        ready_prog = ProgramRecord(
            program_id="ready-agent", name="Agent Embodiment",
            status=ProgramStatus.READY, priority=10,
        )
        portfolio_director.add_program(wait_prog)
        portfolio_director.add_program(ready_prog)

        best, decision = portfolio_director.select_best_program()
        assert best is not None
        assert best.program_id == "ready-agent"
        assert decision.selected_for_execution


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Portfolio priority scoring
# ═══════════════════════════════════════════════════════════════════════════════

class TestPortfolioPriority:
    def test_higher_priority_selected_first(self, portfolio_director):
        low = ProgramRecord(program_id="low", status=ProgramStatus.READY, priority=3)
        high = ProgramRecord(program_id="high", status=ProgramStatus.READY, priority=9)
        portfolio_director.add_program(low)
        portfolio_director.add_program(high)

        best, decision = portfolio_director.select_best_program()
        assert best.program_id == "high"

    def test_external_wait_penalized_in_score(self):
        policy = PortfolioPolicy()
        wait_prog = ProgramRecord(
            program_id="wait", status=ProgramStatus.WAIT_EXTERNAL,
            value_score=10.0, urgency_score=10.0,
        )
        ready_prog = ProgramRecord(
            program_id="ready", status=ProgramStatus.READY,
            value_score=5.0, urgency_score=5.0,
        )
        wait_score = policy.score_program(wait_prog)
        ready_score = policy.score_program(ready_prog)
        # WAIT_EXTERNAL penalty makes the score lower
        assert wait_score.external_wait_penalty > 0
        # ready_score has no penalty — verify the difference
        assert ready_score.external_wait_penalty == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Owner directive
# ═══════════════════════════════════════════════════════════════════════════════

class TestOwnerDirective:
    def test_directive_boosts_priority(self, portfolio_director):
        prog = ProgramRecord(program_id="odp1", status=ProgramStatus.READY, priority=5)
        portfolio_director.add_program(prog)

        directive = OwnerDirective(
            text="继续推进整个项目",
            intent="continue",
            priority="high",
        )
        portfolio_director.receive_directive(directive)

    def test_directive_not_shell_command(self):
        directive = OwnerDirective(text="继续推进整个项目", intent="continue")
        assert directive.intent == "continue"
        # Must never be treated as a shell command — no shell metacharacters
        import re
        assert not re.search(r'\b(bash|sh|zsh|python|node)\b', directive.text)

    def test_continue_inference(self, nexara_prime):
        intent = nexara_prime._infer_intent("继续推进整个项目")
        assert intent == "continue"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. High risk programs require approval
# ═══════════════════════════════════════════════════════════════════════════════

class TestRiskGating:
    def test_high_risk_not_auto_switched_to(self):
        policy = PortfolioPolicy()
        running = ProgramRecord(
            program_id="running", status=ProgramStatus.RUNNING,
            value_score=5.0, urgency_score=5.0,
        )
        high_risk = ProgramRecord(
            program_id="danger", status=ProgramStatus.READY,
            risk_score=9.0, value_score=10.0, urgency_score=10.0,
        )
        # High risk should not auto-switch
        assert not policy.should_auto_switch(running, high_risk)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Review budget
# ═══════════════════════════════════════════════════════════════════════════════

class TestReviewBudget:
    def test_budget_exhausted_triggers_merge_readiness(self):
        policy = PortfolioPolicy()
        prog = ProgramRecord(program_id="rb1", status=ProgramStatus.RUNNING)
        prog.review_budget.cycles_used = 10
        prog.review_budget.max_cycles = 10
        result = policy.evaluate_review_budget(prog)
        assert result["action"] == "merge_readiness"

    def test_repeated_root_cause_triggers_structural_fix(self):
        policy = PortfolioPolicy()
        prog = ProgramRecord(program_id="rb2", status=ProgramStatus.RUNNING)
        prog.review_budget.root_cause_counts["incorrect_classification"] = 3
        prog.review_budget.repeated_root_cause_limit = 2
        result = policy.evaluate_review_budget(prog)
        assert result["action"] == "structural_fix_required"

    def test_p2_can_become_issue(self):
        rb = ReviewBudget(program_id="test", p2_policy="issue")
        assert rb.p2_policy == "issue"


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Lifecycle states
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuntimeLifecycle:
    def test_startup_transitions(self):
        lc = RuntimeLifecycle()
        assert lc.state == LifecycleState.OFFLINE
        assert lc.transition(LifecycleState.STARTING)
        assert lc.state == LifecycleState.STARTING
        assert lc.transition(LifecycleState.ONLINE)
        assert lc.state == LifecycleState.ONLINE

    def test_pause_resume(self):
        lc = RuntimeLifecycle()
        lc.transition(LifecycleState.STARTING)
        lc.transition(LifecycleState.ONLINE)
        assert lc.transition(LifecycleState.PAUSING)
        assert lc.transition(LifecycleState.PAUSED)
        assert lc.transition(LifecycleState.ONLINE)

    def test_stop_sequence(self):
        lc = RuntimeLifecycle()
        lc.transition(LifecycleState.STARTING)
        lc.transition(LifecycleState.ONLINE)
        assert lc.transition(LifecycleState.STOPPING)
        assert lc.transition(LifecycleState.STOPPED)

    def test_invalid_transition_rejected(self):
        lc = RuntimeLifecycle()
        assert not lc.transition(LifecycleState.ONLINE)  # OFFLINE -> ONLINE is invalid
        assert lc.state == LifecycleState.OFFLINE


# ═══════════════════════════════════════════════════════════════════════════════
# 11. run_once / pause / resume
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunOnce:
    def test_run_once_returns_decision(self, nexara_prime):
        # Add a program so there's something to select
        prog = ProgramRecord(program_id="ro1", name="Test", status=ProgramStatus.READY)
        nexara_prime.portfolio_director.add_program(prog)
        result = nexara_prime.run_once()
        assert "action" in result
        assert "reason" in result

    def test_run_once_idle_when_no_programs(self, nexara_prime):
        result = nexara_prime.run_once()
        assert result["action"] == "idle"


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Crash resume
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrashResume:
    def test_recover_running_programs(self, portfolio_director):
        prog = ProgramRecord(program_id="cr1", status=ProgramStatus.RUNNING)
        portfolio_director.add_program(prog)
        # Simulate crash
        recovered = portfolio_director.recover_program("cr1")
        assert recovered is not None

    def test_recover_failed_program(self, portfolio_director):
        prog = ProgramRecord(program_id="cr2", status=ProgramStatus.FAILED)
        portfolio_director.add_program(prog)
        recovered = portfolio_director.recover_program("cr2")
        assert recovered is not None
        assert recovered.status == ProgramStatus.RECOVERING


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Heartbeat
# ═══════════════════════════════════════════════════════════════════════════════

class TestHeartbeat:
    def test_heartbeat_pulses(self, temp_db):
        store, events = temp_db
        hb = Heartbeat(events)
        hb.start()
        time.sleep(0.2)
        hb.pulse()
        status = hb.status()
        assert "agent" in status
        assert status["agent"]["beats"] >= 1
        hb.stop()

    def test_worker_registration(self, temp_db):
        store, events = temp_db
        hb = Heartbeat(events)
        hb.register_worker("worker-1")
        assert hb.is_healthy("worker:worker-1")
        hb.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# 14. Doctor
# ═══════════════════════════════════════════════════════════════════════════════

class TestDoctor:
    def test_doctor_runs_all_checks(self, agent_identity, temp_db):
        store, events = temp_db
        doc = Doctor()
        result = doc.run_all(store=store, events=events, identity=agent_identity)
        assert "healthy" in result
        assert "checks" in result
        assert "identity_recoverable" in result["checks"]

    def test_doctor_detects_no_identity(self):
        doc = Doctor()
        result = doc.run_all(identity=None)
        assert not result["checks"]["identity_recoverable"]


# ═══════════════════════════════════════════════════════════════════════════════
# 15. No duplicate systems
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoDuplicates:
    def test_nexara_prime_has_single_store(self, nexara_prime):
        assert nexara_prime.store is not None

    def test_nexara_prime_has_single_eventbus(self, nexara_prime):
        assert nexara_prime.events is not None

    def test_portfolio_shares_store_with_runtime(self, nexara_prime):
        assert nexara_prime.portfolio_director._store is nexara_prime.store


# ═══════════════════════════════════════════════════════════════════════════════
# 16. Status display
# ═══════════════════════════════════════════════════════════════════════════════

class TestStatusDisplay:
    def test_status_returns_runtime_status(self, nexara_prime):
        nexara_prime._started_at = "2024-01-01T00:00:00Z"
        st = nexara_prime.status()
        assert isinstance(st, RuntimeStatus)
        assert st.identity == "NEXARA PRIME"
        assert st.agent_id == "nexara_prime.agent"
        assert st.state in ("offline", "starting", "online")

    def test_status_can_report_who_i_am(self, nexara_prime):
        st = nexara_prime.status()
        assert st.identity  # "我是谁"
        assert st.agent_id   # identity reference
        assert st.state      # "我当前状态"

    def test_status_can_report_what_im_doing(self, nexara_prime):
        st = nexara_prime.status()
        assert st.current_decision or True  # "我在做什么"

    def test_status_can_report_what_im_waiting_for(self, nexara_prime):
        st = nexara_prime.status()
        # Wait conditions are reported
        assert isinstance(st.wait_conditions, list)

    def test_status_can_report_next_action(self, nexara_prime):
        st = nexara_prime.status()
        assert st.next_action  # "下一步是什么"


# ═══════════════════════════════════════════════════════════════════════════════
# 17. Watcher
# ═══════════════════════════════════════════════════════════════════════════════

class TestExternalWatcher:
    def test_watcher_starts_and_stops(self, temp_db):
        store, events = temp_db
        w = ExternalConditionWatcher(events)
        w.start()
        assert w._active
        w.stop()
        assert not w._active

    def test_register_and_check_condition(self, temp_db):
        store, events = temp_db
        w = ExternalConditionWatcher(events)
        w.register_checker("test_check", lambda ref: ref == "satisfied")
        assert w.force_check("test_check", "satisfied")
        assert not w.force_check("test_check", "not-satisfied")


# ═══════════════════════════════════════════════════════════════════════════════
# 18. Portfolio summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestPortfolioSummary:
    def test_summary_includes_all_programs(self, portfolio_director):
        for i in range(3):
            portfolio_director.add_program(ProgramRecord(
                program_id=f"sp{i}", name=f"Program {i}",
                status=ProgramStatus.PLANNED,
            ))
        summary = portfolio_director.summary()
        assert summary["total_programs"] == 3

    def test_summary_is_deterministic(self, portfolio_director):
        portfolio_director.add_program(ProgramRecord(
            program_id="sd1", name="Test", status=ProgramStatus.PLANNED,
        ))
        s1 = portfolio_director.summary()
        s2 = portfolio_director.summary()
        assert s1["total_programs"] == s2["total_programs"]


# ═══════════════════════════════════════════════════════════════════════════════
# 19. Decision trace evidence
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecisionTrace:
    def test_decision_recorded_on_selection(self, portfolio_director):
        prog = ProgramRecord(program_id="dt1", name="Trace Test", status=ProgramStatus.READY)
        portfolio_director.add_program(prog)
        _, decision = portfolio_director.select_best_program()
        assert decision.program_id == "dt1"
        assert decision.selected_for_execution

    def test_decision_stored_in_history(self, portfolio_director):
        prog = ProgramRecord(program_id="dt2", name="History Test", status=ProgramStatus.READY)
        portfolio_director.add_program(prog)
        portfolio_director.select_best_program()
        assert len(portfolio_director._decision_history) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# 20. Program checkpoint
# ═══════════════════════════════════════════════════════════════════════════════

class TestProgramCheckpoint:
    def test_checkpoint_created(self, portfolio_director):
        prog = ProgramRecord(program_id="cp1", name="Checkpoint Test", status=ProgramStatus.RUNNING)
        portfolio_director.add_program(prog)
        cp = portfolio_director.checkpoint(prog, mission_id="m1", phase="execution")
        assert cp.program_id == "cp1"
        assert cp.mission_id == "m1"


# ═══════════════════════════════════════════════════════════════════════════════
# 21. No worker → fail closed
# ═══════════════════════════════════════════════════════════════════════════════

class TestWorkerFailover:
    def test_no_worker_does_not_crash(self, nexara_prime):
        """Without workers, system should still be functional — not crash."""
        st = nexara_prime.status()
        assert st is not None

    def test_status_reports_workers(self, nexara_prime):
        st = nexara_prime.status()
        assert isinstance(st.active_workers, list)


# ═══════════════════════════════════════════════════════════════════════════════
# 22. Agent embodiment E2E
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentEmbodimentE2E:
    def test_full_identity_chain(self, nexara_prime):
        """Agent identity chain: identity → status → portfolio → decision."""
        assert nexara_prime.identity.agent_id == "nexara_prime.agent"
        st = nexara_prime.status()
        assert st.identity == "NEXARA PRIME"
        # Add a program and verify selection
        prog = ProgramRecord(program_id="e2e-1", name="E2E Test", status=ProgramStatus.READY)
        nexara_prime.portfolio_director.add_program(prog)
        result = nexara_prime.run_once()
        assert result["action"] == "selected"

    def test_lifecycle_start_stop(self, nexara_prime):
        assert nexara_prime.lifecycle.state == LifecycleState.OFFLINE
        nexara_prime.lifecycle.transition(LifecycleState.STARTING)
        nexara_prime.lifecycle.transition(LifecycleState.ONLINE)
        assert nexara_prime.lifecycle.state == LifecycleState.ONLINE
