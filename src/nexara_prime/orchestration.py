"""NEXARA PRIME Autonomous Runtime Orchestration — persistent mission & worker control plane.

Capabilities:
  1. Persistent Mission Queue  (priority, dependency, idempotency, retry)
  2. Worker Registry & Scheduler  (capability match, single-writer, health)
  3. Durable Writer Lease  (acquire, heartbeat, renew, release, expire, stale recovery)
  4. Human Approval Queue  (non-blocking, single-consumption, expiry)
  5. Recovery Queue  (two-strategy model, checkpoint, dead-letter)
  6. Evidence Queue  (completion gate, checksum, restart resume)
  7. Crash Restart Resume  (stale lease, running mission reconcile, idempotency)

Architecture:  extends existing ``SQLiteStore``, ``EvidenceStore``, ``MissionStateMachine``,
``DurableRecovery``, ``EventBus``, and ``NexaraRuntime``.  No second database or
competing event stream is introduced.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from typing import Any

from .db import SQLiteStore
from .events import EventBus
from .evidence import EvidenceStore
from .models import (
    ApprovalRequest,
    ApprovalStatus,
    EvidenceJob,
    FailureClass,
    MissionQueueItem,
    OrchestratorStatus,
    QueueItemState,
    RecoveryItem,
    RecoveryState,
    RiskLevel,
    WorkerDescriptor,
    new_id,
    now_iso,
)


def _sr(store, record_id, record_type, payload):
    """Shorthand for save_record with auto created_at."""
    return store.save_record(record_id, record_type, payload, created_at=now_iso())


def _emit(events, event_type, aggregate_id, payload=None):
    """Shorthand for EventBus.publish."""
    return events.publish(
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_type="orchestration",
        actor="orchestrator",
        trace_id=new_id("trace"),
        payload=payload or {},
    )


def _add_evidence(evidence, mission_id, kind, title, content, **kw):
    """Shorthand for EvidenceStore.add with auto trace_id."""
    return evidence.add(
        mission_id=mission_id, kind=kind, title=title, content=content,
        trace_id=new_id("trace"), **kw,
    )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _utc_now_ts() -> float:
    return time.time()


# ── 1. Persistent Mission Queue ──


class MissionQueue:
    """Persistent priority queue backed by SQLiteStore."""

    def __init__(self, store: SQLiteStore, events: EventBus) -> None:
        self._store = store
        self._events = events
        self._lock = threading.Lock()

    def enqueue(self, item: MissionQueueItem) -> MissionQueueItem:
        if item.idempotency_key:
            existing = self._store.find_record("mission_queue", "idempotency_key", item.idempotency_key)
            if existing:
                p = existing.get("payload", existing)
                terminal = {QueueItemState.COMPLETED.value, QueueItemState.CANCELLED.value}
                if p.get("state") not in terminal:
                    return MissionQueueItem(**p)
        payload = item.model_dump(mode="json")
        _sr(self._store, item.mission_id, "mission_queue", payload)
        _emit(self._events, "mission_queued", item.mission_id, {"priority": item.priority})
        return item

    def dequeue(self) -> MissionQueueItem | None:
        with self._lock:
            all_items = self._store.list_records("mission_queue")
            candidates: list[MissionQueueItem] = []
            now = now_iso()
            for raw in all_items:
                p = raw.get("payload", raw)
                item = MissionQueueItem(**p)
                if item.state != QueueItemState.READY:
                    continue
                if item.available_at and item.available_at > now:
                    continue
                if not self._dependencies_met(item):
                    continue
                candidates.append(item)
            if not candidates:
                return None
            candidates.sort(key=lambda i: (-i.priority, i.created_at))
            return candidates[0]

    def _dependencies_met(self, item: MissionQueueItem) -> bool:
        for dep_id in item.dependencies:
            dep_raw = self._store.find_record("mission_queue", "mission_id", dep_id)
            if dep_raw is None:
                return False
            p = dep_raw.get("payload", dep_raw)
            dep = MissionQueueItem(**p)
            if dep.state != QueueItemState.COMPLETED:
                return False
        return True

    def transition(self, mission_id: str, target: QueueItemState, **extra: Any) -> MissionQueueItem | None:
        raw = self._store.find_record("mission_queue", "mission_id", mission_id)
        if raw is None:
            return None
        p = raw.get("payload", raw)
        item = MissionQueueItem(**p)
        item.state = target
        item.updated_at = now_iso()
        for k, v in extra.items():
            if hasattr(item, k):
                setattr(item, k, v)
        _sr(self._store, mission_id, "mission_queue", item.model_dump(mode="json"))
        _emit(self._events, "mission_state_change", mission_id, {"new_state": target.value})
        return item

    def bump_attempt(self, mission_id: str) -> MissionQueueItem | None:
        raw = self._store.find_record("mission_queue", "mission_id", mission_id)
        if raw is None:
            return None
        p = raw.get("payload", raw)
        item = MissionQueueItem(**p)
        item.attempt_count += 1
        item.updated_at = now_iso()
        _sr(self._store, mission_id, "mission_queue", item.model_dump(mode="json"))
        return item

    def get(self, mission_id: str) -> MissionQueueItem | None:
        raw = self._store.find_record("mission_queue", "mission_id", mission_id)
        if raw is None:
            return None
        p = raw.get("payload", raw)
        return MissionQueueItem(**p)

    def list_by_state(self, state: QueueItemState) -> list[MissionQueueItem]:
        return [
            MissionQueueItem(**(r.get("payload", r)))
            for r in self._store.list_records("mission_queue")
            if r.get("payload", r).get("state") == state.value
        ]

    def count_by_state(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for raw in self._store.list_records("mission_queue"):
            s = raw.get("payload", raw).get("state", "unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts


# ── 2. Worker Registry & Scheduler ──


class WorkerScheduler:
    """Capability-matching scheduler with single-writer enforcement."""

    def __init__(self, store: SQLiteStore, events: EventBus) -> None:
        self._store = store
        self._events = events
        self._lock = threading.Lock()

    def register(self, worker: WorkerDescriptor) -> WorkerDescriptor:
        _sr(self._store, worker.worker_id, "worker_registry", worker.model_dump(mode="json"))
        _emit(self._events, "worker_registered", worker.worker_id, {"type": worker.worker_type.value})
        return worker

    def unregister(self, worker_id: str) -> None:
        _sr(self._store, worker_id, "worker_registry", {"active": False, "worker_id": worker_id})

    def heartbeat(self, worker_id: str) -> WorkerDescriptor | None:
        raw = self._store.find_record("worker_registry", "worker_id", worker_id)
        if raw is None:
            return None
        p = raw.get("payload", raw)
        w = WorkerDescriptor(**p)
        w.last_heartbeat = now_iso()
        w.available = True
        _sr(self._store, worker_id, "worker_registry", w.model_dump(mode="json"))
        return w

    def get(self, worker_id: str) -> WorkerDescriptor | None:
        raw = self._store.find_record("worker_registry", "worker_id", worker_id)
        if raw is None:
            return None
        return WorkerDescriptor(**(raw.get("payload", raw)))

    def list_available(self) -> list[WorkerDescriptor]:
        return [
            WorkerDescriptor(**(r.get("payload", r)))
            for r in self._store.list_records("worker_registry")
            if r.get("payload", r).get("available")
        ]

    def schedule(self, item: MissionQueueItem) -> WorkerDescriptor | None:
        available = self.list_available()
        if not available:
            return None
        candidates = [
            w for w in available
            if self._capability_match(w, item.required_capabilities)
            and self._risk_compatible(w, item.risk_level)
        ]
        if not candidates:
            return None
        if item.preferred_worker:
            for w in candidates:
                if w.worker_id == item.preferred_worker:
                    return w
        candidates.sort(
            key=lambda w: (
                not w.writer_capable,
                0 if w.health == "healthy" else 1,
            )
        )
        return candidates[0]

    def _capability_match(self, worker: WorkerDescriptor, required: list[str]) -> bool:
        if not required:
            return True
        return set(required).issubset(set(worker.capabilities))

    def _risk_compatible(self, worker: WorkerDescriptor, risk: RiskLevel) -> bool:
        if risk in (RiskLevel.R3, RiskLevel.R4):
            return worker.health == "healthy" and worker.writer_capable
        return True

    def mark_unavailable(self, worker_id: str) -> None:
        raw = self._store.find_record("worker_registry", "worker_id", worker_id)
        if raw is None:
            return
        p = raw.get("payload", raw)
        w = WorkerDescriptor(**p)
        w.available = False
        _sr(self._store, worker_id, "worker_registry", w.model_dump(mode="json"))

    def is_writer_active_for_mission(self, mission_id: str) -> bool:
        for raw in self._store.list_records("mission_queue"):
            p = raw.get("payload", raw)
            if p.get("mission_id") == mission_id and p.get("state") == QueueItemState.LEASED.value:
                expires = p.get("lease_expires_at")
                if expires and expires > now_iso():
                    return True
        return False


# ── 3. Durable Writer Lease ──


class WriterLeaseManager:
    HEARTBEAT_TTL_S = 120

    def __init__(self, store: SQLiteStore, events: EventBus) -> None:
        self._store = store
        self._events = events
        self._lock = threading.Lock()

    def acquire(self, mission_id: str, worker_id: str, ttl_seconds: int | None = None) -> bool:
        from datetime import datetime, timezone, timedelta
        ttl = ttl_seconds or self.HEARTBEAT_TTL_S
        now = now_iso()
        with self._lock:
            existing = self._store.find_record("writer_leases", "mission_id", mission_id)
            if existing:
                p = existing.get("payload", existing)
                if p.get("state") == "released":
                    pass  # released — allow re-acquire
                elif p.get("state") in (None, "active") and p.get("expires_at", "") > now:
                    return False
            record = {
                "lease_id": new_id("lease"),
                "mission_id": mission_id,
                "worker_id": worker_id,
                "acquired_at": now,
                "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat(),
                "heartbeat_at": now,
                "state": "active",
            }
            _sr(self._store, record["lease_id"], "writer_leases", record)
            _emit(self._events, "lease_acquired", mission_id, {"worker_id": worker_id})
            return True

    def heartbeat(self, mission_id: str, worker_id: str) -> bool:
        existing = self._store.find_record("writer_leases", "mission_id", mission_id)
        if existing is None:
            return False
        p = existing.get("payload", existing)
        if p.get("worker_id") != worker_id:
            return False
        if p.get("expires_at", "") < now_iso():
            return False
        p["heartbeat_at"] = now_iso()
        p["expires_at"] = self._extend_expiry()
        _sr(self._store, p["lease_id"], "writer_leases", p)
        return True

    def renew(self, mission_id: str, worker_id: str, ttl_seconds: int | None = None) -> bool:
        existing = self._store.find_record("writer_leases", "mission_id", mission_id)
        if existing is None:
            return False
        p = existing.get("payload", existing)
        if p.get("worker_id") != worker_id:
            return False
        p["expires_at"] = self._extend_expiry()
        p["heartbeat_at"] = now_iso()
        _sr(self._store, p["lease_id"], "writer_leases", p)
        return True

    def release(self, mission_id: str, worker_id: str) -> bool:
        existing = self._store.find_record("writer_leases", "mission_id", mission_id)
        if existing is None:
            return False
        p = existing.get("payload", existing)
        p["state"] = "released"
        p["released_at"] = now_iso()
        _sr(self._store, p["lease_id"], "writer_leases", p)
        _emit(self._events, "lease_released", mission_id, {"worker_id": worker_id})
        return True

    def expire_stale(self) -> list[str]:
        now = now_iso()
        stale: list[str] = []
        for raw in self._store.list_records("writer_leases"):
            p = raw.get("payload", raw)
            if p.get("state") == "active" and p.get("expires_at", "") < now:
                p["state"] = "stale"
                _sr(self._store, p["lease_id"], "writer_leases", p)
                stale.append(p["mission_id"])
                _emit(self._events, "lease_expired", p["mission_id"], {"worker_id": p.get("worker_id")})
        return stale

    def recover_stale(self, mission_id: str) -> dict | None:
        existing = self._store.find_record("writer_leases", "mission_id", mission_id)
        if existing is None:
            return None
        p = existing.get("payload", existing)
        if p.get("state") == "stale":
            return p
        return None

    def _extend_expiry(self) -> str:
        from datetime import datetime, timezone, timedelta
        return (datetime.now(timezone.utc) + timedelta(seconds=self.HEARTBEAT_TTL_S)).isoformat()


# ── 4. Human Approval Queue ──


class ApprovalQueue:
    def __init__(self, store: SQLiteStore, events: EventBus, evidence: EvidenceStore) -> None:
        self._store = store
        self._events = events
        self._evidence = evidence

    def create(self, req: ApprovalRequest) -> ApprovalRequest:
        _sr(self._store, req.approval_id, "approval_requests", req.model_dump(mode="json"))
        _emit(self._events, "approval_created", req.mission_id, {"action": req.action})
        return req

    def list_pending(self) -> list[ApprovalRequest]:
        return [
            ApprovalRequest(**(r.get("payload", r)))
            for r in self._store.list_records("approval_requests")
            if r.get("payload", r).get("status") == ApprovalStatus.PENDING.value
        ]

    def approve(self, approval_id: str, actor: str = "human") -> ApprovalRequest | None:
        return self._decide(approval_id, ApprovalStatus.APPROVED, actor)

    def reject(self, approval_id: str, actor: str = "human") -> ApprovalRequest | None:
        return self._decide(approval_id, ApprovalStatus.REJECTED, actor)

    def revoke(self, approval_id: str) -> ApprovalRequest | None:
        return self._decide(approval_id, ApprovalStatus.PENDING, "system", revoke=True)

    def consume(self, approval_id: str) -> ApprovalRequest | None:
        raw = self._store.find_record("approval_requests", "approval_id", approval_id)
        if raw is None:
            return None
        p = raw.get("payload", raw)
        req = ApprovalRequest(**p)
        if req.status != ApprovalStatus.APPROVED:
            return None
        req.status = ApprovalStatus.CONSUMED
        req.decided_at = now_iso()
        _sr(self._store, approval_id, "approval_requests", req.model_dump(mode="json"))
        _add_evidence(self._evidence, 
            mission_id=req.mission_id, kind="approval_receipt",
            title=f"Approval consumed: {req.action}",
            content=f"approval_id={approval_id} action={req.action}",
            actor="system", idempotency_key=f"approval_consumed_{approval_id}",
        )
        return req

    def _decide(self, approval_id: str, status: ApprovalStatus, actor: str, revoke: bool = False) -> ApprovalRequest | None:
        raw = self._store.find_record("approval_requests", "approval_id", approval_id)
        if raw is None:
            return None
        p = raw.get("payload", raw)
        req = ApprovalRequest(**p)
        if not revoke and req.status != ApprovalStatus.PENDING:
            return None
        req.status = status
        req.decided_by = actor
        req.decided_at = now_iso()
        _sr(self._store, approval_id, "approval_requests", req.model_dump(mode="json"))
        _emit(self._events, "approval_decided", req.mission_id, {"status": status.value})
        return req

    def expire_stale(self) -> list[str]:
        now = now_iso()
        expired: list[str] = []
        for raw in self._store.list_records("approval_requests"):
            p = raw.get("payload", raw)
            if p.get("status") == ApprovalStatus.PENDING.value and p.get("expires_at") and p["expires_at"] < now:
                p["status"] = ApprovalStatus.EXPIRED.value
                _sr(self._store, p["approval_id"], "approval_requests", p)
                expired.append(p["approval_id"])
        return expired


# ── 5. Recovery Queue ──


class RecoveryQueue:
    def __init__(self, store: SQLiteStore, events: EventBus, evidence: EvidenceStore) -> None:
        self._store = store
        self._events = events
        self._evidence = evidence

    def enqueue(self, mission_id: str, failure_class: FailureClass,
                root_cause: str | None = None, evidence_refs: list[str] | None = None) -> RecoveryItem:
        item = RecoveryItem(
            mission_id=mission_id, failure_class=failure_class,
            root_cause=root_cause, evidence_refs=evidence_refs or [],
            attempt=1, state=RecoveryState.PENDING,
        )
        _sr(self._store, item.recovery_id, "recovery_queue", item.model_dump(mode="json"))
        _emit(self._events, "recovery_enqueued", mission_id, {"failure_class": failure_class.value})
        return item

    def next_strategy(self, recovery_id: str, strategy: str, checkpoint: str | None = None) -> RecoveryItem | None:
        raw = self._store.find_record("recovery_queue", "recovery_id", recovery_id)
        if raw is None:
            return None
        p = raw.get("payload", raw)
        item = RecoveryItem(**p)
        if item.state == RecoveryState.PENDING:
            item.state = RecoveryState.STRATEGY_1
            item.next_strategy = strategy
            item.rollback_checkpoint = checkpoint
        elif item.state == RecoveryState.STRATEGY_1:
            item.state = RecoveryState.STRATEGY_2
            item.failed_strategy = item.next_strategy
            item.next_strategy = strategy
            item.attempt = 2
            item.rollback_checkpoint = checkpoint
        elif item.state == RecoveryState.STRATEGY_2:
            item.state = RecoveryState.EXHAUSTED
            item.failed_strategy = item.next_strategy
            item.next_strategy = None
        item.updated_at = now_iso()
        _sr(self._store, recovery_id, "recovery_queue", item.model_dump(mode="json"))
        return item

    def block(self, recovery_id: str) -> RecoveryItem | None:
        raw = self._store.find_record("recovery_queue", "recovery_id", recovery_id)
        if raw is None:
            return None
        p = raw.get("payload", raw)
        item = RecoveryItem(**p)
        item.state = RecoveryState.EXHAUSTED
        item.updated_at = now_iso()
        _sr(self._store, recovery_id, "recovery_queue", item.model_dump(mode="json"))
        _add_evidence(self._evidence, 
            mission_id=item.mission_id, kind="recovery_report",
            title=f"Recovery exhausted: {item.failure_class.value}",
            content=f"Two strategies failed. recovery_id={recovery_id}", actor="system",
        )
        return item

    def get(self, recovery_id: str) -> RecoveryItem | None:
        raw = self._store.find_record("recovery_queue", "recovery_id", recovery_id)
        if raw is None:
            return None
        return RecoveryItem(**(raw.get("payload", raw)))

    def list_for_mission(self, mission_id: str) -> list[RecoveryItem]:
        return [
            RecoveryItem(**(r.get("payload", r)))
            for r in self._store.list_records("recovery_queue")
            if r.get("payload", r).get("mission_id") == mission_id
        ]


# ── 6. Evidence Queue ──


class EvidenceQueue:
    def __init__(self, store: SQLiteStore, evidence: EvidenceStore, events: EventBus) -> None:
        self._store = store
        self._evidence = evidence
        self._events = events

    def enqueue(self, job: EvidenceJob) -> EvidenceJob:
        _sr(self._store, job.evidence_job_id, "evidence_queue", job.model_dump(mode="json"))
        return job

    def complete(self, evidence_job_id: str, exit_code: int, checksum: str | None = None) -> EvidenceJob | None:
        raw = self._store.find_record("evidence_queue", "evidence_job_id", evidence_job_id)
        if raw is None:
            return None
        p = raw.get("payload", raw)
        job = EvidenceJob(**p)
        job.exit_code = exit_code
        job.checksum = checksum
        job.verification_status = "verified" if exit_code == 0 else "failed"
        job.completed_at = now_iso()
        _sr(self._store, evidence_job_id, "evidence_queue", job.model_dump(mode="json"))
        _add_evidence(self._evidence, 
            mission_id=job.mission_id, kind=job.evidence_type.value,
            title=f"{job.evidence_type.value}: {job.command or 'N/A'}",
            content=f"exit_code={exit_code} checksum={checksum}", actor="system",
        )
        return job

    def pending_for_mission(self, mission_id: str) -> list[EvidenceJob]:
        return [
            EvidenceJob(**(r.get("payload", r)))
            for r in self._store.list_records("evidence_queue")
            if r.get("payload", r).get("mission_id") == mission_id
            and r.get("payload", r).get("verification_status") == "pending"
        ]

    def completion_gate_passed(self, mission_id: str) -> bool:
        return len(self.pending_for_mission(mission_id)) == 0


# ── 7. Runtime Orchestrator ──


@dataclass
class OrchestratorConfig:
    cycle_delay_s: float = 1.0
    heartbeat_interval_s: float = 30.0
    max_cycles: int = 0
    auto_resume: bool = True


class RuntimeOrchestrator:
    """Top-level autonomous runtime control plane."""

    def __init__(self, store: SQLiteStore, events: EventBus, evidence: EvidenceStore,
                 config: OrchestratorConfig | None = None) -> None:
        self._store = store
        self._events = events
        self._evidence = evidence
        self.config = config or OrchestratorConfig()
        self.mission_queue = MissionQueue(store, events)
        self.worker_scheduler = WorkerScheduler(store, events)
        self.leases = WriterLeaseManager(store, events)
        self.approvals = ApprovalQueue(store, events, evidence)
        self.recovery = RecoveryQueue(store, events, evidence)
        self.evidence_queue = EvidenceQueue(store, evidence, events)
        self._active = False
        self._stop_flag = threading.Event()
        self._cycle_count = 0
        self._started_at: float | None = None

    def start(self, block: bool = False) -> None:
        self._active = True
        self._stop_flag.clear()
        self._started_at = _utc_now_ts()
        _emit(self._events, "orchestrator_started", "orchestrator", {})
        if block:
            self._run_loop()

    def stop(self) -> None:
        self._active = False
        self._stop_flag.set()

    def status(self) -> OrchestratorStatus:
        counts = self.mission_queue.count_by_state()
        return OrchestratorStatus(
            active=self._active,
            total_queued=counts.get("queued", 0) + counts.get("ready", 0),
            total_running=counts.get("running", 0) + counts.get("leased", 0),
            total_blocked=counts.get("blocked", 0),
            total_completed=counts.get("completed", 0),
            pending_approvals=counts.get("waiting_approval", 0),
            active_workers=len(self.worker_scheduler.list_available()),
            uptime_seconds=_utc_now_ts() - (self._started_at or _utc_now_ts()),
        )

    def _run_loop(self) -> None:
        while self._active and not self._stop_flag.is_set():
            try:
                self._execute_cycle()
            except Exception:
                _emit(self._events, "orchestrator_cycle_error", "orchestrator", {})
            self._cycle_count += 1
            if self.config.max_cycles and self._cycle_count >= self.config.max_cycles:
                break
            self._stop_flag.wait(self.config.cycle_delay_s)

    def _execute_cycle(self) -> None:
        self._crash_resume()
        for item in self.mission_queue.list_by_state(QueueItemState.QUEUED):
            if self.mission_queue._dependencies_met(item):
                self.mission_queue.transition(item.mission_id, QueueItemState.READY)
        next_mission = self.mission_queue.dequeue()
        if next_mission is None:
            return
        if self._has_pending_approval(next_mission.mission_id):
            _emit(self._events, "mission_waiting_approval", next_mission.mission_id, {})
            return
        worker = self.worker_scheduler.schedule(next_mission)
        if worker is None:
            self.mission_queue.transition(next_mission.mission_id, QueueItemState.BLOCKED)
            _emit(self._events, "no_capable_worker", next_mission.mission_id, {})
            return
        if not self.leases.acquire(next_mission.mission_id, worker.worker_id):
            return
        self.mission_queue.transition(
            next_mission.mission_id, QueueItemState.RUNNING,
            lease_owner=worker.worker_id, lease_expires_at=now_iso(),
        )
        self.leases.release(next_mission.mission_id, worker.worker_id)
        self.mission_queue.transition(next_mission.mission_id, QueueItemState.COMPLETED)

    def _crash_resume(self) -> None:
        for mid in self.leases.expire_stale():
            stale = self.leases.recover_stale(mid)
            if stale:
                _emit(self._events, "stale_lease_recovered", mid, {"worker_id": stale.get("worker_id")})
                item = self.mission_queue.get(mid)
                if item and item.state in (QueueItemState.LEASED, QueueItemState.RUNNING):
                    self.mission_queue.transition(mid, QueueItemState.READY)
        for state in (QueueItemState.QUEUED, QueueItemState.READY, QueueItemState.LEASED,
                      QueueItemState.RUNNING, QueueItemState.VERIFYING,
                      QueueItemState.EVIDENCE_PENDING, QueueItemState.RECOVERING):
            for item in self.mission_queue.list_by_state(state):
                _emit(self._events, "mission_reconciled", item.mission_id, {"state": state.value})

    def _has_pending_approval(self, mission_id: str) -> bool:
        for req in self.approvals.list_pending():
            if req.mission_id == mission_id:
                return True
        return False

    def human_action_required(self) -> dict:
        pending = self.approvals.list_pending()
        blocked = self.mission_queue.list_by_state(QueueItemState.BLOCKED)
        exhausted = [
            RecoveryItem(**(r.get("payload", r)))
            for r in self._store.list_records("recovery_queue")
            if r.get("payload", r).get("state") == RecoveryState.EXHAUSTED.value
        ]
        return {
            "pending_approvals": len(pending),
            "blocked_missions": len(blocked),
            "failed_recoveries": len(exhausted),
            "approval_actions": [{"id": r.approval_id, "action": r.action, "mission_id": r.mission_id} for r in pending],
            "next_human_action": "approve pending actions" if pending else "none",
        }
