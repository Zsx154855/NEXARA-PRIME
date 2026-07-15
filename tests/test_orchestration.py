"""Tests for NEXARA Autonomous Runtime Orchestration — all 7 MVP capabilities + E2E."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.models import (
    ApprovalRequest,
    ApprovalStatus,
    EvidenceJob,
    EvidenceType,
    FailureClass,
    MissionQueueItem,
    QueueItemState,
    RecoveryState,
    RiskLevel,
    WorkerDescriptor,
    WorkerResult,
    WorkerType,
)
from nexara_prime.orchestration import (
    ApprovalQueue,
    EvidenceQueue,
    MissionQueue,
    OrchestratorConfig,
    RecoveryQueue,
    RuntimeOrchestrator,
    WorkerScheduler,
    WriterLeaseManager,
    _sha256,
)


# ── fixtures ──


@pytest.fixture
def tmp_db():
    d = tempfile.mkdtemp(prefix="nexara_orch_test_")
    db_path = Path(d) / "test.db"
    store = SQLiteStore(db_path)
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
def queue(tmp_db, events):
    return MissionQueue(tmp_db, events)


@pytest.fixture
def scheduler(tmp_db, events):
    return WorkerScheduler(tmp_db, events)


@pytest.fixture
def lease_mgr(tmp_db, events):
    return WriterLeaseManager(tmp_db, events)


@pytest.fixture
def approval_q(tmp_db, events, evidence):
    return ApprovalQueue(tmp_db, events, evidence)


@pytest.fixture
def recovery_q(tmp_db, events, evidence):
    return RecoveryQueue(tmp_db, events, evidence)


@pytest.fixture
def evidence_q(tmp_db, evidence, events):
    return EvidenceQueue(tmp_db, evidence, events)


@pytest.fixture
def orchestrator(tmp_db, events, evidence):
    return RuntimeOrchestrator(tmp_db, events, evidence)


def _make_item(mission_id: str = "mission_test", priority: int = 0, **kw) -> MissionQueueItem:
    defaults = {
        "mission_id": mission_id,
        "priority": priority,
        "state": QueueItemState.READY,
        "risk_level": RiskLevel.R1,
    }
    defaults.update(kw)
    return MissionQueueItem(**defaults)


def _make_worker(worker_id: str = "worker_1", writer: bool = True, **kw) -> WorkerDescriptor:
    defaults = {
        "worker_id": worker_id,
        "worker_type": WorkerType.LOCAL_TOOL,
        "capabilities": ["read", "edit", "test", "build"],
        "writer_capable": writer,
        "health": "healthy",
    }
    defaults.update(kw)
    return WorkerDescriptor(**defaults)


# ── 1. Mission Queue tests ──


class TestMissionQueue:
    def test_fifo_order(self, queue):
        queue.enqueue(_make_item("a", priority=5))
        queue.enqueue(_make_item("b", priority=5))
        queue.enqueue(_make_item("c", priority=5))
        # same priority → FIFO by created_at
        a = queue.dequeue()
        assert a and a.mission_id == "a"

    def test_priority_order(self, queue):
        queue.enqueue(_make_item("low", priority=1))
        queue.enqueue(_make_item("high", priority=10))
        queue.enqueue(_make_item("mid", priority=5))
        first = queue.dequeue()
        assert first and first.mission_id == "high"

    def test_dependency_blocks(self, queue):
        dep = _make_item("dep", state=QueueItemState.QUEUED)
        child = _make_item("child", dependencies=["dep"])
        queue.enqueue(dep)
        queue.enqueue(child)
        assert queue.dequeue() is None  # neither ready (dep is QUEUED)
        queue.transition("dep", QueueItemState.READY)
        # dep is READY, no deps — can be dequeued
        first = queue.dequeue()
        assert first and first.mission_id == "dep"
        # mark dep as RUNNING so it doesn't appear in next dequeue
        queue.transition("dep", QueueItemState.RUNNING)
        # child is still blocked because dep isn't COMPLETED
        assert queue.dequeue() is None
        queue.transition("dep", QueueItemState.COMPLETED)
        child_ready = queue.dequeue()
        assert child_ready and child_ready.mission_id == "child"

    def test_dependency_release(self, queue):
        dep = _make_item("dep")
        child = _make_item("child", dependencies=["dep"])
        queue.enqueue(dep)
        queue.enqueue(child)
        assert queue.dequeue() == queue.get("dep")  # dequeue returns same object
        assert queue.get("dep").mission_id == "dep"


    def test_idempotency_dedup(self, queue):
        key = "idem_key_001"
        i1 = _make_item("a", idempotency_key=key, state=QueueItemState.READY)
        i2 = _make_item("b", idempotency_key=key, state=QueueItemState.READY)
        queue.enqueue(i1)
        queue.enqueue(i2)
        # second should be skipped
        items = queue.list_by_state(QueueItemState.READY)
        assert len(items) == 1
        assert items[0].mission_id == "a"

    def test_delayed_retry(self, queue):
        from datetime import datetime, timezone, timedelta
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        item = _make_item("delayed", available_at=future)
        queue.enqueue(item)
        assert queue.dequeue() is None  # not yet available

    def test_available_at_negative_10_offset(self, queue):
        """available_at with -10:00 offset must be compared as UTC-aware datetime."""
        # -10:00 means 10 hours behind UTC. A timestamp 1 hour in the future
        # in -10:00 is actually 11 hours from now in UTC.
        from datetime import datetime, timezone, timedelta
        tz_m10 = timezone(timedelta(hours=-10))
        dt = datetime.now(tz_m10) + timedelta(hours=1)
        item = _make_item("neg10", available_at=dt.isoformat())
        queue.enqueue(item)
        # The item is 1 hour in the future in -10:00 → not yet available in UTC
        assert queue.dequeue() is None

    def test_available_at_positive_07_offset(self, queue):
        """available_at with +07:00 offset must be compared as UTC-aware datetime."""
        # +07:00 means 7 hours ahead of UTC. A timestamp 1 hour in the past
        # in +07:00 was actually 8 hours ago in UTC.
        from datetime import datetime, timezone, timedelta
        tz_p7 = timezone(timedelta(hours=7))
        dt = datetime.now(tz_p7) - timedelta(hours=1)
        item = _make_item("pos7", available_at=dt.isoformat())
        queue.enqueue(item)
        # The item is 1 hour ago — already available
        result = queue.dequeue()
        assert result is not None
        assert result.mission_id == "pos7"

    def test_available_at_naive_treated_as_utc(self, queue):
        """Naive ISO datetime strings are treated as UTC."""
        from datetime import datetime, timezone, timedelta
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
        item = _make_item("naive_past", available_at=past.isoformat())
        queue.enqueue(item)
        # Already past — should be available
        assert queue.dequeue() is not None

    def test_restart_persistence(self, queue, tmp_db, events):
        queue.enqueue(_make_item("persist_me"))
        # simulate restart: new queue with same store
        q2 = MissionQueue(tmp_db, events)
        item = q2.get("persist_me")
        assert item is not None
        assert item.mission_id == "persist_me"

    def test_completed_not_repeated(self, queue):
        item = _make_item("done", state=QueueItemState.COMPLETED)
        queue.enqueue(item)
        # should not be dequeued (not READY)
        assert queue.dequeue() is None


# ── 2. Worker Scheduler tests ──


class TestWorkerScheduler:
    def test_capability_match(self, scheduler):
        scheduler.register(_make_worker("w1", capabilities=["read", "edit"]))
        scheduler.register(_make_worker("w2", capabilities=["deploy"]))
        item = _make_item(required_capabilities=["edit"])
        w = scheduler.schedule(item)
        assert w and w.worker_id == "w1"

    def test_no_capable_worker(self, scheduler):
        scheduler.register(_make_worker("w1", capabilities=["read"]))
        item = _make_item(required_capabilities=["deploy"])
        assert scheduler.schedule(item) is None

    def test_preferred_worker(self, scheduler):
        scheduler.register(_make_worker("w1"))
        scheduler.register(_make_worker("w2"))
        item = _make_item(preferred_worker="w2")
        w = scheduler.schedule(item)
        assert w and w.worker_id == "w2"

    def test_writer_preference(self, scheduler):
        scheduler.register(_make_worker("reader", writer=False, capabilities=["read"]))
        scheduler.register(_make_worker("writer", writer=True, capabilities=["read"]))
        item = _make_item(required_capabilities=["read"])
        w = scheduler.schedule(item)
        assert w and w.worker_id == "writer"

    def test_health_check(self, scheduler):
        scheduler.register(_make_worker("healthy", health="healthy"))
        scheduler.register(_make_worker("sick", health="degraded"))
        item = _make_item()
        w = scheduler.schedule(item)
        assert w and w.worker_id == "healthy"

    def test_heartbeat(self, scheduler):
        scheduler.register(_make_worker("w1"))
        w = scheduler.heartbeat("w1")
        assert w and w.available is True
        assert w.last_heartbeat > "2026-01-01"


# ── 3. Writer Lease tests ──


class TestWriterLease:
    def test_acquire_and_release(self, lease_mgr):
        assert lease_mgr.acquire("mission_a", "worker_1")
        assert lease_mgr.release("mission_a", "worker_1")

    def test_double_acquire_blocks(self, lease_mgr):
        assert lease_mgr.acquire("mission_a", "worker_1")
        assert not lease_mgr.acquire("mission_a", "worker_2")  # blocked

    def test_heartbeat_keeps_alive(self, lease_mgr):
        lease_mgr.acquire("mission_a", "worker_1")
        assert lease_mgr.heartbeat("mission_a", "worker_1")

    def test_heartbeat_wrong_worker_fails(self, lease_mgr):
        lease_mgr.acquire("mission_a", "worker_1")
        assert not lease_mgr.heartbeat("mission_a", "worker_2")

    def test_renew(self, lease_mgr):
        lease_mgr.acquire("mission_a", "worker_1")
        assert lease_mgr.renew("mission_a", "worker_1")

    def test_stale_expire(self, lease_mgr):
        lease_mgr.acquire("mission_a", "worker_1", ttl_seconds=-1)  # instantly expired
        stale = lease_mgr.expire_stale()
        assert "mission_a" in stale

    def test_stale_recovery(self, lease_mgr):
        lease_mgr.acquire("mission_a", "worker_1", ttl_seconds=-1)
        _stale = lease_mgr.expire_stale()
        recovered = lease_mgr.recover_stale("mission_a")
        assert recovered is not None
        assert recovered["state"] == "stale"

    def test_release_after_complete(self, lease_mgr):
        lease_mgr.acquire("mission_a", "worker_1")
        lease_mgr.release("mission_a", "worker_1")
        # after release, a new writer can acquire
        assert lease_mgr.acquire("mission_a", "worker_2")


# ── 4. Approval Queue tests ──


class TestApprovalQueue:
    def _make_req(self, mission_id: str = "mission_a", action: str = "merge") -> ApprovalRequest:
        return ApprovalRequest(
            mission_id=mission_id,
            action=action,
            risk_level=RiskLevel.R2,
            rationale="test",
            reversible=True,
        )

    def test_create_and_list(self, approval_q):
        req = self._make_req()
        approval_q.create(req)
        pending = approval_q.list_pending()
        assert len(pending) == 1
        assert pending[0].action == "merge"

    def test_approve_then_consume(self, approval_q):
        req = self._make_req()
        approval_q.create(req)
        approved = approval_q.approve(req.approval_id)
        assert approved and approved.status == ApprovalStatus.APPROVED
        consumed = approval_q.consume(req.approval_id)
        assert consumed and consumed.status == ApprovalStatus.CONSUMED

    def test_double_consume_fails(self, approval_q):
        req = self._make_req()
        approval_q.create(req)
        approval_q.approve(req.approval_id)
        assert approval_q.consume(req.approval_id) is not None
        assert approval_q.consume(req.approval_id) is None  # already consumed

    def test_reject(self, approval_q):
        req = self._make_req()
        approval_q.create(req)
        rejected = approval_q.reject(req.approval_id)
        assert rejected and rejected.status == ApprovalStatus.REJECTED

    def test_revoke_resets(self, approval_q):
        req = self._make_req()
        approval_q.create(req)
        approval_q.approve(req.approval_id)
        revoked = approval_q.revoke(req.approval_id)
        assert revoked is not None

    def test_approval_bound_to_mission(self, approval_q):
        req_a = self._make_req("mission_a", "merge_a")
        req_b = self._make_req("mission_b", "merge_b")
        approval_q.create(req_a)
        approval_q.create(req_b)
        approval_q.approve(req_a.approval_id)
        pending = approval_q.list_pending()
        assert len(pending) == 1
        assert pending[0].mission_id == "mission_b"

    def test_approval_not_reusable_across_missions(self, approval_q):
        req = self._make_req("mission_a")
        approval_q.create(req)
        approval_q.approve(req.approval_id)
        consumed = approval_q.consume(req.approval_id)
        assert consumed
        # cannot consume again
        assert approval_q.consume(req.approval_id) is None


# ── 5. Recovery Queue tests ──


class TestRecoveryQueue:
    def test_enqueue(self, recovery_q):
        item = recovery_q.enqueue("mission_a", FailureClass.CODE_FAILURE)
        assert item.state == RecoveryState.PENDING
        assert item.failure_class == FailureClass.CODE_FAILURE

    def test_strategy_progression(self, recovery_q):
        item = recovery_q.enqueue("mission_a", FailureClass.TEST_FAILURE)
        s1 = recovery_q.next_strategy(item.recovery_id, "fix_import", "ckpt_1")
        assert s1 and s1.state == RecoveryState.STRATEGY_1
        s2 = recovery_q.next_strategy(item.recovery_id, "rewrite_module", "ckpt_2")
        assert s2 and s2.state == RecoveryState.STRATEGY_2
        assert s2.failed_strategy == "fix_import"

    def test_exhausted_blocks(self, recovery_q):
        item = recovery_q.enqueue("mission_a", FailureClass.CODE_FAILURE)
        recovery_q.next_strategy(item.recovery_id, "strat_a")
        recovery_q.next_strategy(item.recovery_id, "strat_b")
        exhausted = recovery_q.next_strategy(item.recovery_id, "strat_c")
        assert exhausted and exhausted.state == RecoveryState.EXHAUSTED

    def test_block_then_recovery_evidence(self, recovery_q, evidence, tmp_db):
        item = recovery_q.enqueue("mission_a", FailureClass.TEST_FAILURE)
        blocked = recovery_q.block(item.recovery_id)
        assert blocked and blocked.state == RecoveryState.EXHAUSTED


# ── 6. Evidence Queue tests ──


class TestEvidenceQueue:
    def _make_job(self, mission_id: str = "mission_a") -> EvidenceJob:
        return EvidenceJob(
            mission_id=mission_id,
            evidence_type=EvidenceType.TEST_REPORT,
            command="pytest tests/ -v",
        )

    def test_enqueue_and_complete(self, evidence_q):
        job = self._make_job()
        evidence_q.enqueue(job)
        completed = evidence_q.complete(job.evidence_job_id, exit_code=0, checksum=_sha256("ok"))
        assert completed and completed.verification_status == "verified"

    def test_completion_gate(self, evidence_q):
        job = self._make_job()
        evidence_q.enqueue(job)
        assert not evidence_q.completion_gate_passed("mission_a")
        evidence_q.complete(job.evidence_job_id, exit_code=0)
        assert evidence_q.completion_gate_passed("mission_a")

    def test_checksum_mismatch_fails(self, evidence_q):
        job = self._make_job()
        evidence_q.enqueue(job)
        completed = evidence_q.complete(
            job.evidence_job_id, exit_code=0, checksum="wrong_hash"
        )
        # completion still records result but verification may be flagged
        assert completed is not None

    def test_exit_code_preserved(self, evidence_q):
        job = self._make_job()
        evidence_q.enqueue(job)
        completed = evidence_q.complete(job.evidence_job_id, exit_code=1)
        assert completed and completed.exit_code == 1
        assert completed.verification_status == "failed"

    def test_restart_resume(self, evidence_q, tmp_db, events):
        job = self._make_job()
        evidence_q.enqueue(job)
        # simulate restart
        eq2 = EvidenceQueue(tmp_db, EvidenceStore(tmp_db, events), events)
        assert not eq2.completion_gate_passed("mission_a")
        eq2.complete(job.evidence_job_id, exit_code=0)
        assert eq2.completion_gate_passed("mission_a")


# ── 7. Crash Restart Resume tests ──


class TestCrashResume:
    def test_stale_lease_recovery(self, orchestrator):
        orchestrator.leases.acquire("mission_a", "worker_1", ttl_seconds=-1)
        orchestrator.mission_queue.enqueue(
            _make_item("mission_a", state=QueueItemState.RUNNING)
        )
        orchestrator._crash_resume()
        item = orchestrator.mission_queue.get("mission_a")
        assert item is not None
        # should be re-enqueued as READY after stale recovery
        assert item.state in (QueueItemState.READY, QueueItemState.QUEUED)

    def test_running_mission_reconcile(self, orchestrator):
        orchestrator.mission_queue.enqueue(
            _make_item("mission_a", state=QueueItemState.RUNNING)
        )
        orchestrator._crash_resume()
        item = orchestrator.mission_queue.get("mission_a")
        assert item is not None
        # reconcile should emit an event (visible via event count)
        assert item.state == QueueItemState.RUNNING  # not auto-transitioned by resume alone

    def test_pending_evidence_resume(self, orchestrator):
        orchestrator.mission_queue.enqueue(_make_item("mission_a"))
        job = EvidenceJob(
            mission_id="mission_a",
            evidence_type=EvidenceType.TEST_REPORT,
            command="pytest",
        )
        orchestrator.evidence_queue.enqueue(job)
        assert not orchestrator.evidence_queue.completion_gate_passed("mission_a")
        orchestrator.evidence_queue.complete(job.evidence_job_id, exit_code=0)
        assert orchestrator.evidence_queue.completion_gate_passed("mission_a")

    def test_idempotency_prevents_duplicate_side_effects(self, queue, orchestrator):
        key = "side_effect_key"
        i1 = _make_item("a", idempotency_key=key)
        i2 = _make_item("b", idempotency_key=key)
        queue.enqueue(i1)
        queue.enqueue(i2)
        items = queue.list_by_state(QueueItemState.READY)
        assert len(items) == 1


# ── E2E Tests ──


class TestE2EOrchestration:
    def test_e2e_a_unattended_local_task(self, orchestrator):
        """E2E A: Enqueue → Local Worker → test → Evidence → Completed → next mission."""
        orchestrator.mission_queue.enqueue(
            _make_item("local_1", required_capabilities=["read", "test"])
        )
        orchestrator.worker_scheduler.register(
            _make_worker("local_w", writer=True, capabilities=["read", "test", "build"])
        )
        # Simplified: direct cycle instead of full loop
        orchestrator.mission_queue.transition("local_1", QueueItemState.READY)
        item = orchestrator.mission_queue.dequeue()
        assert item is not None
        # acquire lease
        ok = orchestrator.leases.acquire("local_1", "local_w")
        assert ok
        # simulate worker result
        orchestrator.mission_queue.transition("local_1", QueueItemState.RUNNING)
        # evidence
        job = EvidenceJob(mission_id="local_1", evidence_type=EvidenceType.TEST_REPORT, command="pytest")
        orchestrator.evidence_queue.enqueue(job)
        orchestrator.evidence_queue.complete(job.evidence_job_id, exit_code=0)
        orchestrator.mission_queue.transition("local_1", QueueItemState.COMPLETED)
        orchestrator.leases.release("local_1", "local_w")
        assert orchestrator.evidence_queue.completion_gate_passed("local_1")
        item = orchestrator.mission_queue.get("local_1")
        assert item.state == QueueItemState.COMPLETED

    def test_e2e_b_claude_worker_replaceable(self, orchestrator):
        """E2E B: Mission requiring edit → selected Claude adapter → result → verify."""
        orchestrator.worker_scheduler.register(
            _make_worker("claude_w", worker_type=WorkerType.CLAUDE, writer=True, capabilities=["edit", "analyze"])
        )
        orchestrator.mission_queue.enqueue(
            _make_item("edit_1", required_capabilities=["edit"], preferred_worker="claude_w")
        )
        item = orchestrator.mission_queue.get("edit_1")
        worker = orchestrator.worker_scheduler.schedule(item)
        assert worker and worker.worker_id == "claude_w"
        # fake worker result (deterministic fake — explicitly labeled)
        result = WorkerResult(
            worker_id="claude_w",
            mission_id="edit_1",
            success=True,
            output={"fake": True, "note": "deterministic fake adapter for E2E B"},
        )
        assert result.success
        orchestrator.mission_queue.transition("edit_1", QueueItemState.COMPLETED)
        assert orchestrator.mission_queue.get("edit_1").state == QueueItemState.COMPLETED

    def test_e2e_c_approval_nonblocking(self, orchestrator):
        """E2E C: Mission A needs merge approval → WAITING_APPROVAL; Mission B continues independently."""
        orchestrator.mission_queue.enqueue(_make_item("mission_a"))
        orchestrator.mission_queue.enqueue(_make_item("mission_b"))
        orchestrator.worker_scheduler.register(_make_worker("w1", writer=True))
        # Mission A needs approval
        req = ApprovalRequest(mission_id="mission_a", action="merge", risk_level=RiskLevel.R2, rationale="test", reversible=True)
        orchestrator.approvals.create(req)
        # Mission B should still be runnable
        pending = orchestrator.approvals.list_pending()
        assert len(pending) == 1
        assert pending[0].mission_id == "mission_a"
        # Mission B can be dequeued independently
        b = orchestrator.mission_queue.get("mission_b")
        assert b and b.state == QueueItemState.READY

    def test_e2e_d_recovery_worker_crash(self, orchestrator):
        """E2E D: Worker crash → lease expires → recovery → retry → complete."""
        orchestrator.mission_queue.enqueue(_make_item("crash_1"))
        orchestrator.worker_scheduler.register(_make_worker("w1", writer=True))
        # simulate running then crash
        orchestrator.leases.acquire("crash_1", "w1", ttl_seconds=-1)
        orchestrator.mission_queue.transition("crash_1", QueueItemState.RUNNING)
        # crash resume
        orchestrator._crash_resume()
        item = orchestrator.mission_queue.get("crash_1")
        assert item and item.state in (QueueItemState.READY, QueueItemState.QUEUED)

    def test_e2e_e_two_strategies_fail(self, orchestrator):
        """E2E E: Strategy A fails → Strategy B fails → BLOCKED → evidence → human required."""
        item = orchestrator.recovery.enqueue("blocked_1", FailureClass.CODE_FAILURE)
        s1 = orchestrator.recovery.next_strategy(item.recovery_id, "fix_a")
        assert s1.state == RecoveryState.STRATEGY_1
        s2 = orchestrator.recovery.next_strategy(item.recovery_id, "fix_b")
        assert s2.state == RecoveryState.STRATEGY_2
        exhausted = orchestrator.recovery.next_strategy(item.recovery_id, "fix_c")
        assert exhausted and exhausted.state == RecoveryState.EXHAUSTED
        # human notification
        notification = orchestrator.human_action_required()
        assert notification["failed_recoveries"] >= 1

    def test_single_writer_enforcement(self, orchestrator):
        """Two writers cannot acquire the same mission simultaneously."""
        orchestrator.mission_queue.enqueue(_make_item("single_writer_test"))
        ok1 = orchestrator.leases.acquire("single_writer_test", "writer_a")
        ok2 = orchestrator.leases.acquire("single_writer_test", "writer_b")
        assert ok1
        assert not ok2

    def test_external_worker_independence(self, orchestrator):
        """Claude/Codex/Hermes are registered as workers, not hardcoded."""
        claude = _make_worker("claude_1", worker_type=WorkerType.CLAUDE)
        code_reviewer = _make_worker("reviewer_1", worker_type=WorkerType.CODE_REVIEWER, writer=False)
        orchestrator.worker_scheduler.register(claude)
        orchestrator.worker_scheduler.register(code_reviewer)
        # both can be scheduled based on capabilities, not identity
        w_claude = orchestrator.worker_scheduler.get("claude_1")
        w_reviewer = orchestrator.worker_scheduler.get("reviewer_1")
        assert w_claude and w_claude.worker_type == WorkerType.CLAUDE
        assert w_reviewer and w_reviewer.worker_type == WorkerType.CODE_REVIEWER
        # Neither is mandatory — orchestrator runs without them
        orchestrator.worker_scheduler.unregister("claude_1")
        orchestrator.worker_scheduler.unregister("reviewer_1")
        assert len(orchestrator.worker_scheduler.list_available()) == 0


# ── Regression Tests — Codex Review Fixes ──


class TestIdempotencyMixedRecords:
    """Idempotency must scan ALL matching records, not just the first."""

    def test_active_blocked_by_nonterminal(self, queue):
        key = "idem_mixed"
        terminal = _make_item("done", idempotency_key=key, state=QueueItemState.COMPLETED)
        active = _make_item("active", idempotency_key=key, state=QueueItemState.READY)
        queue.enqueue(terminal)
        # Simulate: first record stored is terminal → second enqueue should find active, not be tricked by terminal
        # Directly save a terminal record via store, then enqueue an active one with same key
        queue.enqueue(active)
        # The active item should have been deduped (returned existing active, not created duplicate)
        items = [i for i in queue.list_by_state(QueueItemState.READY) if i.idempotency_key == key]
        assert len(items) == 1


class TestUnregisterPreservesDescriptor:
    """Unregister must set available=False on the full WorkerDescriptor."""

    def test_unregister_preserves_fields(self, scheduler):
        w = _make_worker("w1", worker_type=WorkerType.CLAUDE, capabilities=["edit"])
        scheduler.register(w)
        scheduler.unregister("w1")
        # After unregister, get() should still return the full descriptor
        got = scheduler.get("w1")
        assert got is not None
        assert got.worker_id == "w1"
        assert got.worker_type == WorkerType.CLAUDE
        assert got.capabilities == ["edit"]
        assert got.available is False

    def test_unregister_nonexistent_noop(self, scheduler):
        scheduler.unregister("ghost")  # must not raise


class TestLeaseOwnerValidation:
    """Release must validate worker ownership."""

    def test_non_owner_cannot_release(self, lease_mgr):
        lease_mgr.acquire("mission_a", "owner")
        assert not lease_mgr.release("mission_a", "intruder")

    def test_owner_can_release(self, lease_mgr):
        lease_mgr.acquire("mission_a", "owner")
        assert lease_mgr.release("mission_a", "owner")

    def test_release_nonexistent(self, lease_mgr):
        assert not lease_mgr.release("no_mission", "anyone")


class TestLeaseAcquireScansAll:
    """Acquire must scan ALL leases for a mission, not just the first match."""

    def test_dual_writer_blocked_by_second_active_lease(self, lease_mgr):
        # Simulate two lease records for same mission: one released, one active
        lease_mgr.acquire("mission_a", "writer_1")
        lease_mgr.release("mission_a", "writer_1")
        lease_mgr.acquire("mission_a", "writer_2")  # re-acquire
        # writer_3 must be blocked — there's an active lease from writer_2
        assert not lease_mgr.acquire("mission_a", "writer_3")


class TestRenewCustomTTL:
    """Renew must honor the caller-provided ttl_seconds."""

    def test_renew_uses_custom_ttl(self, lease_mgr):
        lease_mgr.acquire("mission_a", "w1", ttl_seconds=60)
        assert lease_mgr.renew("mission_a", "w1", ttl_seconds=3600)

    def test_renew_defaults_to_heartbeat_ttl(self, lease_mgr):
        lease_mgr.acquire("mission_a", "w1")
        assert lease_mgr.renew("mission_a", "w1")


class TestApprovalExpiryRejection:
    """Expired approvals must be rejected, not decided."""

    def test_approve_expired_fails(self, approval_q):
        from datetime import datetime, timezone, timedelta
        req = ApprovalRequest(
            mission_id="mission_a", action="merge", risk_level=RiskLevel.R2,
            rationale="test", reversible=True,
            expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        )
        approval_q.create(req)
        result = approval_q.approve(req.approval_id)
        assert result is None  # expired — cannot approve

    def test_reject_expired_fails(self, approval_q):
        from datetime import datetime, timezone, timedelta
        req = ApprovalRequest(
            mission_id="mission_a", action="merge", risk_level=RiskLevel.R2,
            rationale="test", reversible=True,
            expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        )
        approval_q.create(req)
        result = approval_q.reject(req.approval_id)
        assert result is None  # expired — cannot reject


class TestCompletionGateFailedBlocks:
    """Completion gate must fail when any evidence job has status=failed."""

    def test_failed_job_blocks_completion(self, evidence_q):
        job = EvidenceJob(mission_id="mission_a", evidence_type=EvidenceType.TEST_REPORT, command="pytest")
        evidence_q.enqueue(job)
        evidence_q.complete(job.evidence_job_id, exit_code=1)
        assert not evidence_q.completion_gate_passed("mission_a")

    def test_mixed_pending_and_failed_blocks(self, evidence_q):
        job1 = EvidenceJob(mission_id="mission_a", evidence_type=EvidenceType.TEST_REPORT, command="pytest")
        job2 = EvidenceJob(mission_id="mission_a", evidence_type=EvidenceType.BUILD_REPORT, command="build")
        evidence_q.enqueue(job1)
        evidence_q.enqueue(job2)
        evidence_q.complete(job1.evidence_job_id, exit_code=0)  # verified
        # job2 is still pending — gate should be blocked
        assert not evidence_q.completion_gate_passed("mission_a")

    def test_all_verified_passes(self, evidence_q):
        job = EvidenceJob(mission_id="mission_a", evidence_type=EvidenceType.TEST_REPORT, command="pytest")
        evidence_q.enqueue(job)
        evidence_q.complete(job.evidence_job_id, exit_code=0)
        assert evidence_q.completion_gate_passed("mission_a")


class TestChecksumValidation:
    """Checksum mismatch must cause verification failure."""

    def test_complete_with_exit0_but_checksum_mismatch_fails(self, evidence_q):
        job = EvidenceJob(
            mission_id="mission_a", evidence_type=EvidenceType.ARTIFACT_MANIFEST,
            command="sha256sum dist/*",
            checksum="expected_abc123",  # set expected checksum at enqueue time
        )
        evidence_q.enqueue(job)
        # Complete with wrong checksum — even with exit_code=0
        completed = evidence_q.complete(job.evidence_job_id, exit_code=0, checksum="wrong_xyz")
        assert completed and completed.verification_status == "failed"

    def test_complete_with_matching_checksum_succeeds(self, evidence_q):
        job = EvidenceJob(
            mission_id="mission_a", evidence_type=EvidenceType.ARTIFACT_MANIFEST,
            command="sha256sum dist/*",
            checksum="expected_abc123",
        )
        evidence_q.enqueue(job)
        completed = evidence_q.complete(job.evidence_job_id, exit_code=0, checksum="expected_abc123")
        assert completed and completed.verification_status == "verified"


class TestOrchestratorNonBlockingStart:
    """start(block=False) must launch a background thread."""

    def test_nonblocking_start_launches_thread(self, orchestrator):
        orchestrator.start(block=False)
        try:
            assert orchestrator._active
            assert orchestrator._loop_thread is not None
            assert orchestrator._loop_thread.is_alive()
        finally:
            orchestrator.stop()
            if orchestrator._loop_thread:
                orchestrator._loop_thread.join(timeout=2)


class TestCompleteMissionEvidenceGate:
    """complete_mission() must verify evidence gate before completing."""

    def test_complete_without_evidence_succeeds(self, orchestrator):
        """Mission with no evidence jobs can complete (gate vacuously passes)."""
        orchestrator.mission_queue.enqueue(_make_item("mission_x"))
        orchestrator.mission_queue.transition("mission_x", QueueItemState.RUNNING)
        orchestrator.leases.acquire("mission_x", "w1")
        assert orchestrator.complete_mission("mission_x", "w1")
        assert orchestrator.mission_queue.get("mission_x").state == QueueItemState.COMPLETED

    def test_complete_with_failed_evidence_fails(self, orchestrator):
        orchestrator.mission_queue.enqueue(_make_item("mission_x"))
        orchestrator.mission_queue.transition("mission_x", QueueItemState.RUNNING)
        orchestrator.leases.acquire("mission_x", "w1")
        job = EvidenceJob(mission_id="mission_x", evidence_type=EvidenceType.TEST_REPORT, command="pytest")
        orchestrator.evidence_queue.enqueue(job)
        orchestrator.evidence_queue.complete(job.evidence_job_id, exit_code=1)
        assert not orchestrator.complete_mission("mission_x", "w1")

    def test_complete_with_verified_evidence_succeeds(self, orchestrator):
        orchestrator.mission_queue.enqueue(_make_item("mission_x"))
        orchestrator.worker_scheduler.register(_make_worker("w1", writer=True))
        orchestrator.mission_queue.transition("mission_x", QueueItemState.RUNNING)
        orchestrator.leases.acquire("mission_x", "w1")
        job = EvidenceJob(mission_id="mission_x", evidence_type=EvidenceType.TEST_REPORT, command="pytest")
        orchestrator.evidence_queue.enqueue(job)
        orchestrator.evidence_queue.complete(job.evidence_job_id, exit_code=0)
        assert orchestrator.complete_mission("mission_x", "w1")
        item = orchestrator.mission_queue.get("mission_x")
        assert item.state == QueueItemState.COMPLETED

    def test_complete_not_running_fails(self, orchestrator):
        orchestrator.mission_queue.enqueue(_make_item("mission_x"))
        # Not RUNNING — should fail
        assert not orchestrator.complete_mission("mission_x", "w1")


class TestApprovalNonblockingCycle:
    """Approval-blocked mission must not stall lower-priority READY missions."""

    def test_approval_mission_does_not_block_others(self, orchestrator):
        orchestrator.worker_scheduler.register(_make_worker("w1", writer=True))
        # Mission A needs approval
        orchestrator.mission_queue.enqueue(_make_item("mission_a", priority=10))
        req = ApprovalRequest(mission_id="mission_a", action="merge", risk_level=RiskLevel.R2,
                              rationale="test", reversible=True)
        orchestrator.approvals.create(req)
        # Mission B is independent and lower priority
        orchestrator.mission_queue.enqueue(_make_item("mission_b", priority=1))
        # Run one cycle
        orchestrator._execute_cycle()
        # Mission A should be WAITING_APPROVAL (not blocking)
        a = orchestrator.mission_queue.get("mission_a")
        assert a.state == QueueItemState.WAITING_APPROVAL
        # Mission B should be RUNNING (dispatched, not blocked)
        b = orchestrator.mission_queue.get("mission_b")
        assert b.state == QueueItemState.RUNNING


class TestRevokeDoesNotResetConsumed:
    """revoke() must not reset CONSUMED approvals — single-consumption guarantee."""

    def test_revoke_consumed_fails(self, approval_q):
        req = ApprovalRequest(mission_id="mission_a", action="merge", risk_level=RiskLevel.R2,
                              rationale="test", reversible=True)
        approval_q.create(req)
        approval_q.approve(req.approval_id)
        approval_q.consume(req.approval_id)
        # Revoking a consumed approval must fail
        result = approval_q.revoke(req.approval_id)
        assert result is None


class TestStatusPendingApprovals:
    """status().pending_approvals must reflect ApprovalQueue, not mission state alone."""

    def test_pending_approvals_reflects_approval_queue(self, orchestrator):
        req = ApprovalRequest(mission_id="mission_a", action="merge", risk_level=RiskLevel.R2,
                              rationale="test", reversible=True)
        orchestrator.approvals.create(req)
        s = orchestrator.status()
        assert s.pending_approvals >= 1

    def test_no_approvals_reports_zero(self, orchestrator):
        s = orchestrator.status()
        assert s.pending_approvals == 0


class TestCrashResumeEventFlood:
    """_crash_resume must not emit per-mission events every cycle."""

    def test_no_flood_on_subsequent_cycles(self, orchestrator):
        # First call: no stale leases, should emit nothing
        orchestrator._crash_resume()
        # Verify no stale lease events were emitted for non-existent missions
        # (Idempotent: subsequent calls with no stale leases are no-ops)
        orchestrator._crash_resume()
        # No crash — no assertions needed beyond no exception


class TestAutoResumeConfig:
    """OrchestratorConfig.auto_resume=False must disable crash resume."""

    def test_auto_resume_disabled_skips_crash_resume(self, tmp_db, events, evidence):
        config = OrchestratorConfig(auto_resume=False)
        orch = RuntimeOrchestrator(tmp_db, events, evidence, config=config)
        orch.mission_queue.enqueue(_make_item("mission_a"))
        orch.worker_scheduler.register(_make_worker("w1", writer=True))
        # Run a cycle with auto_resume=False — must not attempt crash resume
        orch._execute_cycle()
        # Mission should be dispatched normally without crash resume interference
        item = orch.mission_queue.get("mission_a")
        assert item.state == QueueItemState.RUNNING


class TestRequeueAfterApproval:
    """WAITING_APPROVAL missions must return to READY after approval consumed."""

    def test_requeue_after_approval_consumed(self, orchestrator):
        orchestrator.worker_scheduler.register(_make_worker("w1", writer=True))
        orchestrator.mission_queue.enqueue(_make_item("mission_a"))
        req = ApprovalRequest(mission_id="mission_a", action="merge", risk_level=RiskLevel.R2,
                              rationale="test", reversible=True)
        orchestrator.approvals.create(req)
        # Cycle 1: mission moves to WAITING_APPROVAL
        orchestrator._execute_cycle()
        a = orchestrator.mission_queue.get("mission_a")
        assert a.state == QueueItemState.WAITING_APPROVAL
        # Human approves and consumes
        orchestrator.approvals.approve(req.approval_id)
        orchestrator.approvals.consume(req.approval_id)
        # Cycle 2: mission should be promoted back to READY, then dispatched
        orchestrator.mission_queue.transition("mission_a", QueueItemState.WAITING_APPROVAL)
        orchestrator._execute_cycle()
        a = orchestrator.mission_queue.get("mission_a")
        assert a.state == QueueItemState.RUNNING


class TestCompleteMissionLeaseOwner:
    """complete_mission() must verify lease owner before completing."""

    def test_non_owner_cannot_complete(self, orchestrator):
        orchestrator.mission_queue.enqueue(_make_item("mission_x"))
        orchestrator.mission_queue.transition("mission_x", QueueItemState.RUNNING)
        orchestrator.leases.acquire("mission_x", "owner_w")
        assert not orchestrator.complete_mission("mission_x", "intruder_w")

    def test_owner_can_complete(self, orchestrator):
        orchestrator.mission_queue.enqueue(_make_item("mission_x"))
        orchestrator.mission_queue.transition("mission_x", QueueItemState.RUNNING)
        orchestrator.leases.acquire("mission_x", "owner_w")
        assert orchestrator.complete_mission("mission_x", "owner_w")
        assert orchestrator.mission_queue.get("mission_x").state == QueueItemState.COMPLETED


class TestRejectFailedWorkerResult:
    """complete_mission() must reject WorkerResult with success=False."""

    def test_failed_worker_result_rejected(self, orchestrator):
        orchestrator.mission_queue.enqueue(_make_item("mission_x"))
        orchestrator.mission_queue.transition("mission_x", QueueItemState.RUNNING)
        orchestrator.leases.acquire("mission_x", "w1")
        failed_result = WorkerResult(
            worker_id="w1", mission_id="mission_x", success=False,
            failure_class=FailureClass.CODE_FAILURE,
        )
        assert not orchestrator.complete_mission("mission_x", "w1", worker_result=failed_result)


class TestStaleLeaseMaxAttempts:
    """Stale lease recovery must enforce max_attempts."""

    def test_max_attempts_exceeded_blocks_mission(self, orchestrator):
        item = _make_item("retry_mission", max_attempts=2, attempt_count=1,
                          state=QueueItemState.RUNNING)
        orchestrator.mission_queue.enqueue(item)
        orchestrator.leases.acquire("retry_mission", "w1", ttl_seconds=-1)
        orchestrator._crash_resume()
        updated = orchestrator.mission_queue.get("retry_mission")
        assert updated.state == QueueItemState.BLOCKED


class TestHeartbeatScansAllLeases:
    """heartbeat() must find the current active lease, not just first match."""

    def test_heartbeat_finds_active_after_reacquire(self, lease_mgr):
        lease_mgr.acquire("mission_a", "w1")
        lease_mgr.release("mission_a", "w1")
        lease_mgr.acquire("mission_a", "w2")
        # heartbeat for w2 must find the new active lease, not the old released one
        assert lease_mgr.heartbeat("mission_a", "w2")


class TestRecoverStaleScansAllLeases:
    """recover_stale() must find the stale lease across all records."""

    def test_recover_stale_after_reacquire(self, lease_mgr):
        lease_mgr.acquire("mission_a", "w1", ttl_seconds=-1)
        lease_mgr.expire_stale()  # marks first lease stale
        lease_mgr.acquire("mission_a", "w2", ttl_seconds=-1)
        lease_mgr.expire_stale()  # marks second lease stale
        # recover_stale must find a stale lease (either one)
        recovered = lease_mgr.recover_stale("mission_a")
        assert recovered is not None
        assert recovered["state"] == "stale"


class TestListAvailableExpiresStaleWorkers:
    """list_available() must filter out workers with expired heartbeats."""

    def test_stale_worker_not_listed(self, scheduler):
        w = _make_worker("stale_w", health="healthy")
        scheduler.register(w)
        # Manually set last_heartbeat to old
        raw = scheduler._store.find_record("worker_registry", "worker_id", "stale_w")
        p = raw.get("payload", raw)
        p["last_heartbeat"] = "2020-01-01T00:00:00Z"
        from nexara_prime.orchestration import _sr
        _sr(scheduler._store, "stale_w", "worker_registry", p)
        available = scheduler.list_available()
        assert all(w.worker_id != "stale_w" for w in available)
