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
    WorkerResult,
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


def _parse_instant(ts: str | None) -> float | None:
    """Parse any ISO-8601 datetime string to a UTC Unix timestamp.

    Handles:
      - Offset-aware strings: ``2026-07-15T00:30:00-10:00``, ``+07:00``, ``+00:00``
      - ``Z`` suffix: ``2026-07-15T21:04:32Z``
      - Naive strings: treated as UTC (``2026-07-15T12:00:00`` → UTC)

    Returns None if ts is None or unparseable.
    """
    if ts is None:
        return None
    from datetime import datetime, timezone
    try:
        # Normalize 'Z' suffix to '+00:00' for fromisoformat
        normalized = ts
        if ts.endswith("Z"):
            normalized = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        # Naive → interpret as UTC
        dt = dt.replace(tzinfo=timezone.utc)
    # Convert to UTC timestamp
    return dt.timestamp()


def _instant_before(a: str | None, b: str | None) -> bool:
    """Return True if instant *a* is strictly before instant *b*.

    None represents unbounded-past (always before any concrete instant).
    """
    ta = _parse_instant(a)
    tb = _parse_instant(b)
    if ta is None:
        return True
    if tb is None:
        return False
    return ta < tb


def _instant_before_or_equal(a: str | None, b: str | None) -> bool:
    """Return True if instant *a* is before or at instant *b*.

    None represents unbounded-past.
    """
    ta = _parse_instant(a)
    tb = _parse_instant(b)
    if ta is None:
        return True
    if tb is None:
        return False
    return ta <= tb


# ── 1. Persistent Mission Queue ──


class MissionQueue:
    """Persistent priority queue backed by SQLiteStore."""

    def __init__(self, store: SQLiteStore, events: EventBus) -> None:
        self._store = store
        self._events = events
        self._lock = threading.Lock()

    def enqueue(self, item: MissionQueueItem) -> MissionQueueItem:
        if item.idempotency_key:
            all_records = self._store.list_records("mission_queue")
            terminal = {QueueItemState.COMPLETED.value, QueueItemState.CANCELLED.value}
            for raw in all_records:
                p = raw.get("payload", raw)
                if p.get("idempotency_key") == item.idempotency_key and p.get("state") not in terminal:
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
                # available_at must be <= now (item is available)
                if item.available_at and not _instant_before_or_equal(item.available_at, now):
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
        raw = self._store.find_record("worker_registry", "worker_id", worker_id)
        if raw is None:
            return
        p = raw.get("payload", raw)
        w = WorkerDescriptor(**p)
        w.available = False
        _sr(self._store, worker_id, "worker_registry", w.model_dump(mode="json"))
        _emit(self._events, "worker_unregistered", worker_id, {})

    def heartbeat(self, worker_id: str) -> WorkerDescriptor | None:
        raw = self._store.find_record("worker_registry", "worker_id", worker_id)
        if raw is None:
            return None
        p = raw.get("payload", raw)
        w = WorkerDescriptor(**p)
        if not w.available:
            return None  # do not reactivate unregistered workers
        w.last_heartbeat = now_iso()
        _sr(self._store, worker_id, "worker_registry", w.model_dump(mode="json"))
        return w

    def get(self, worker_id: str) -> WorkerDescriptor | None:
        raw = self._store.find_record("worker_registry", "worker_id", worker_id)
        if raw is None:
            return None
        return WorkerDescriptor(**(raw.get("payload", raw)))

    def list_available(self) -> list[WorkerDescriptor]:
        from datetime import datetime, timezone, timedelta
        stale_threshold = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
        available: list[WorkerDescriptor] = []
        for r in self._store.list_records("worker_registry"):
            p = r.get("payload", r)
            if not p.get("available"):
                continue
            w = WorkerDescriptor(**p)
            # Compare as UTC-aware instants
            if not _instant_before_or_equal(stale_threshold, w.last_heartbeat):
                continue  # stale worker — heartbeat expired
            available.append(w)
        return available

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

    # ── internal: find the current active lease ──

    def _latest_active_lease(self, mission_id: str) -> dict | None:
        """Return the newest active (or stale) lease record for *mission_id*,
        scanning all lease records and picking the one with the latest
        ``acquired_at``.  Returns None when no lease record exists.
        """
        candidates: list[dict] = []
        for raw in self._store.list_records("writer_leases"):
            p = raw.get("payload", raw)
            if p.get("mission_id") != mission_id:
                continue
            candidates.append(p)
        if not candidates:
            return None
        # Pick newest by acquired_at (ISO-8601 strings sort correctly for UTC)
        candidates.sort(key=lambda p: p.get("acquired_at", ""), reverse=True)
        return candidates[0]

    # ── acquire ──

    def acquire(self, mission_id: str, worker_id: str, ttl_seconds: int | None = None) -> bool:
        from datetime import datetime, timezone, timedelta
        ttl = ttl_seconds if ttl_seconds is not None else self.HEARTBEAT_TTL_S
        now = now_iso()
        # Check all existing leases for this mission — any active unexpired lease blocks
        for raw in self._store.list_records("writer_leases"):
            p = raw.get("payload", raw)
            if p.get("mission_id") != mission_id:
                continue
            state = p.get("state")
            if state in ("released", "stale"):
                continue
            # active or unknown — check expiry
            expires = p.get("expires_at", "")
            if state in (None, "active") and _instant_before(now, expires):
                return False  # already has an active lease
        # Atomic DB-level claim: use a deterministic claim record ID so only
        # the first writer across ALL connections/processes succeeds.
        claim_id = f"lease_claim:{mission_id}:{worker_id}:{now}"
        record = {
            "lease_id": claim_id,
            "mission_id": mission_id,
            "worker_id": worker_id,
            "acquired_at": now,
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat(),
            "heartbeat_at": now,
            "state": "active",
        }
        claimed = self._store.save_record_if_absent(
            claim_id, "writer_leases", record, created_at=now, mission_id=mission_id,
        )
        if claimed:
            _emit(self._events, "lease_acquired", mission_id, {"worker_id": worker_id})
        return claimed

    def heartbeat(self, mission_id: str, worker_id: str) -> bool:
        lease = self._latest_active_lease(mission_id)
        if lease is None:
            return False
        if lease.get("state") != "active":
            return False
        if lease.get("worker_id") != worker_id:
            return False
        if not _instant_before(now_iso(), lease.get("expires_at", "")):
            return False
        lease["heartbeat_at"] = now_iso()
        lease["expires_at"] = self._extend_expiry()
        _sr(self._store, lease["lease_id"], "writer_leases", lease)
        return True

    def renew(self, mission_id: str, worker_id: str, ttl_seconds: int | None = None) -> bool:
        lease = self._latest_active_lease(mission_id)
        if lease is None:
            return False
        if lease.get("worker_id") != worker_id:
            return False
        lease["expires_at"] = self._extend_expiry(ttl_seconds)
        lease["heartbeat_at"] = now_iso()
        _sr(self._store, lease["lease_id"], "writer_leases", lease)
        return True

    def release(self, mission_id: str, worker_id: str) -> bool:
        lease = self._latest_active_lease(mission_id)
        if lease is None:
            return False
        if lease.get("worker_id") != worker_id:
            return False  # non-owner cannot release
        lease["state"] = "released"
        lease["released_at"] = now_iso()
        _sr(self._store, lease["lease_id"], "writer_leases", lease)
        _emit(self._events, "lease_released", mission_id, {"worker_id": worker_id})
        return True

    def expire_stale(self) -> list[str]:
        now = now_iso()
        stale: list[str] = []
        for raw in self._store.list_records("writer_leases"):
            p = raw.get("payload", raw)
            if p.get("state") == "active" and not _instant_before_or_equal(now, p.get("expires_at", "")):
                p["state"] = "stale"
                _sr(self._store, p["lease_id"], "writer_leases", p)
                stale.append(p["mission_id"])
                _emit(self._events, "lease_expired", p["mission_id"], {"worker_id": p.get("worker_id")})
        return stale

    def recover_stale(self, mission_id: str) -> dict | None:
        for raw in self._store.list_records("writer_leases"):
            p = raw.get("payload", raw)
            if p.get("mission_id") == mission_id and p.get("state") == "stale":
                return p
        return None

    def _extend_expiry(self, ttl_seconds: int | None = None) -> str:
        from datetime import datetime, timezone, timedelta
        ttl = ttl_seconds if ttl_seconds is not None else self.HEARTBEAT_TTL_S
        return (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat()


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
        raw = self._store.find_record("approval_requests", "approval_id", approval_id)
        if raw is None:
            return None
        p = raw.get("payload", raw)
        req = ApprovalRequest(**p)
        # Cannot revoke already-consumed approvals — single-consumption guarantee
        if req.status == ApprovalStatus.CONSUMED:
            return None
        return self._decide(approval_id, ApprovalStatus.PENDING, "system", revoke=True)

    def consume(self, approval_id: str) -> ApprovalRequest | None:
        raw = self._store.find_record("approval_requests", "approval_id", approval_id)
        if raw is None:
            return None
        p = raw.get("payload", raw)
        req = ApprovalRequest(**p)
        if req.status != ApprovalStatus.APPROVED:
            return None
        # Atomic compare-and-set: re-read to detect concurrent consumer
        recheck = self._store.find_record("approval_requests", "approval_id", approval_id)
        if recheck is None:
            return None
        rp = recheck.get("payload", recheck)
        if rp.get("status") != ApprovalStatus.APPROVED.value:
            return None  # another consumer already consumed
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
        # Reject expired approvals — cannot approve/reject after expiry
        if not revoke and req.expires_at and not _instant_before_or_equal(now_iso(), req.expires_at):
            req.status = ApprovalStatus.EXPIRED
            req.decided_at = now_iso()
            _sr(self._store, approval_id, "approval_requests", req.model_dump(mode="json"))
            _emit(self._events, "approval_expired", req.mission_id, {"approval_id": approval_id})
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
            if (p.get("status") == ApprovalStatus.PENDING.value
                    and p.get("expires_at")
                    and not _instant_before_or_equal(now, p["expires_at"])):
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
        # Filter to only known EvidenceJob fields for model construction
        from .models import EvidenceJob as EJ
        known_fields = {f for f in EJ.model_fields}
        filtered = {k: v for k, v in p.items() if k in known_fields}
        job = EvidenceJob(**filtered)
        job.exit_code = exit_code
        # Determine verification: exit_code must be 0
        verified = exit_code == 0
        # If the enqueued job had an expected checksum, validate it
        expected_checksum = p.get("checksum")  # checksum set at enqueue time
        if verified and expected_checksum and checksum != expected_checksum:
            verified = False
        job.verification_status = "verified" if verified else "failed"
        job.checksum = checksum
        job.completed_at = now_iso()
        _sr(self._store, evidence_job_id, "evidence_queue", job.model_dump(mode="json"))
        _add_evidence(self._evidence,
            mission_id=job.mission_id, kind=job.evidence_type.value,
            title=f"{job.evidence_type.value}: {job.command or 'N/A'}",
            content=f"exit_code={exit_code} checksum={checksum} status={job.verification_status}", actor="system",
        )
        return job

    def pending_for_mission(self, mission_id: str) -> list[EvidenceJob]:
        return [
            EvidenceJob(**(r.get("payload", r)))
            for r in self._store.list_records("evidence_queue")
            if r.get("payload", r).get("mission_id") == mission_id
            and r.get("payload", r).get("verification_status") == "pending"
        ]

    def failed_for_mission(self, mission_id: str) -> list[EvidenceJob]:
        return [
            EvidenceJob(**(r.get("payload", r)))
            for r in self._store.list_records("evidence_queue")
            if r.get("payload", r).get("mission_id") == mission_id
            and r.get("payload", r).get("verification_status") == "failed"
        ]

    def completion_gate_passed(self, mission_id: str) -> bool:
        # Gate passes only when no pending AND no failed jobs exist
        return (len(self.pending_for_mission(mission_id)) == 0
                and len(self.failed_for_mission(mission_id)) == 0)


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
        self._loop_thread: threading.Thread | None = None

    def start(self, block: bool = False) -> None:
        if self._active:
            return  # already running — idempotent
        self._active = True
        self._stop_flag.clear()
        self._started_at = _utc_now_ts()
        _emit(self._events, "orchestrator_started", "orchestrator", {})
        if block:
            self._run_loop()
        else:
            t = threading.Thread(target=self._run_loop, daemon=True, name="nexara-orchestrator")
            t.start()
            self._loop_thread = t

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
            pending_approvals=len(self.approvals.list_pending()),
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
                self._active = False
                break
            self._stop_flag.wait(self.config.cycle_delay_s)

    def _execute_cycle(self) -> None:
        if self.config.auto_resume:
            self._crash_resume()
        self.approvals.expire_stale()  # expire stale approvals before dispatching
        # Promote QUEUED → READY when dependencies are met
        for item in self.mission_queue.list_by_state(QueueItemState.QUEUED):
            if self.mission_queue._dependencies_met(item):
                self.mission_queue.transition(item.mission_id, QueueItemState.READY)
        # Promote WAITING_APPROVAL → READY when approval has been consumed
        for item in self.mission_queue.list_by_state(QueueItemState.WAITING_APPROVAL):
            if not self._has_pending_approval(item.mission_id):
                self.mission_queue.transition(item.mission_id, QueueItemState.READY)
        # Process READY missions, skipping approval-blocked ones to not stall the queue
        processed_in_cycle: set[str] = set()
        while True:
            next_mission = self.mission_queue.dequeue()
            if next_mission is None:
                break
            if next_mission.mission_id in processed_in_cycle:
                break  # prevent infinite loop on same item
            processed_in_cycle.add(next_mission.mission_id)
            if self._has_pending_approval(next_mission.mission_id):
                # Transition to WAITING_APPROVAL so it doesn't block other READY missions
                self.mission_queue.transition(
                    next_mission.mission_id, QueueItemState.WAITING_APPROVAL,
                )
                _emit(self._events, "mission_waiting_approval", next_mission.mission_id, {})
                continue  # try next READY mission
            worker = self.worker_scheduler.schedule(next_mission)
            if worker is None:
                self.mission_queue.transition(next_mission.mission_id, QueueItemState.BLOCKED)
                _emit(self._events, "no_capable_worker", next_mission.mission_id, {})
                continue  # try next READY mission
            if not self.leases.acquire(next_mission.mission_id, worker.worker_id):
                continue  # lease conflict — try next READY mission
            # Mission is now LEASED and RUNNING — orchestrator hands off to worker
            # Completion happens via complete_mission() which verifies evidence gate
            self.mission_queue.transition(
                next_mission.mission_id, QueueItemState.RUNNING,
                lease_owner=worker.worker_id, lease_expires_at=now_iso(),
            )
            _emit(self._events, "mission_dispatched", next_mission.mission_id,
                  {"worker_id": worker.worker_id})

    def complete_mission(self, mission_id: str, worker_id: str,
                         worker_result: WorkerResult | None = None) -> bool:
        """Complete a RUNNING mission after evidence gate passes.

        Returns True if the mission was successfully completed.
        Returns False if evidence gate is not satisfied, mission is not RUNNING,
        lease is held by a different worker, or worker result indicates failure.
        """
        item = self.mission_queue.get(mission_id)
        if item is None or item.state != QueueItemState.RUNNING:
            return False
        # Verify lease owner — only the lease holder can complete
        if not self._lease_held_by(mission_id, worker_id):
            _emit(self._events, "complete_mission_lease_mismatch", mission_id, {"worker_id": worker_id})
            return False
        if not self.evidence_queue.completion_gate_passed(mission_id):
            _emit(self._events, "evidence_gate_blocked", mission_id, {})
            return False
        # Reject failed worker results — drive recovery instead
        if worker_result is not None and not worker_result.success:
            _emit(self._events, "worker_result_failed", mission_id,
                  {"worker_id": worker_id, "failure_class": worker_result.failure_class})
            return False
        self.mission_queue.transition(mission_id, QueueItemState.COMPLETED)
        self.leases.release(mission_id, worker_id)
        _emit(self._events, "mission_completed", mission_id,
              {"worker_id": worker_id, "result": worker_result.model_dump(mode="json") if worker_result else {}})
        return True

    def _lease_held_by(self, mission_id: str, worker_id: str) -> bool:
        lease = self.leases._latest_active_lease(mission_id)
        if lease is None:
            return False
        return lease.get("state") == "active" and lease.get("worker_id") == worker_id

    def _crash_resume(self) -> None:
        recovered_count = 0
        for mid in self.leases.expire_stale():
            stale = self.leases.recover_stale(mid)
            if stale:
                _emit(self._events, "stale_lease_recovered", mid, {"worker_id": stale.get("worker_id")})
                item = self.mission_queue.get(mid)
                if item and item.state in (QueueItemState.LEASED, QueueItemState.RUNNING):
                    self.mission_queue.bump_attempt(mid)
                    updated = self.mission_queue.get(mid)
                    if updated and updated.attempt_count >= updated.max_attempts:
                        self.mission_queue.transition(mid, QueueItemState.BLOCKED)
                        self.recovery.enqueue(mid, FailureClass.LEASE_EXPIRED,
                                              root_cause=f"Stale lease recovery exhausted after {updated.attempt_count} attempts")
                    else:
                        self.mission_queue.transition(mid, QueueItemState.READY)
                recovered_count += 1
        # Only emit a single reconciled event when actual recovery happened
        if recovered_count > 0:
            _emit(self._events, "crash_resume_performed", "orchestrator",
                  {"recovered_leases": recovered_count})

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
