"""Autonomous Supervisor — plans, dispatches, monitors, and auto-advances missions."""
from __future__ import annotations

import hashlib
import json
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..db import SQLiteStore
from ..events import EventBus
from ..evidence import EvidenceStore
from ..models import MissionQueueItem, QueueItemState, RiskLevel
from ..orchestration import RuntimeOrchestrator

from .execution_gateway import ExecutionGateway
from .permission_broker import PermissionBroker
from .recovery_engine import RecoveryEngine, RecoveryStrategy
from .cost_optimizer import CostOptimizer
from .health_monitor import HealthMonitor


class SupervisorState(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    DISPATCHING = "dispatching"
    MONITORING = "monitoring"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class SupervisorConfig:
    cycle_delay_s: float = 2.0
    max_concurrent_missions: int = 3
    auto_advance: bool = True
    max_cycles_per_mission: int = 50
    health_check_interval_s: float = 30.0
    evidence_on_completion: bool = True
    stale_lease_timeout_s: float = 300.0
    approval_expiry_timeout_s: float = 3600.0
    max_consecutive_errors: int = 10
    default_lease_duration_s: float = 600.0


class AutonomousSupervisor:
    """Top-level autonomous supervisor.

    Responsibilities:
    - Read current state from .nexara/*
    - Select next mission from the program loop
    - Select worker via scheduler for unpinned missions
    - Dispatch through ExecutionGateway (which enforces PermissionBroker)
    - Handle WorkerResult: success→complete, retryable→recover, fatal→BLOCKED
    - Monitor worker health and progress
    - Trigger recovery on failures
    - Write evidence on completion (idempotent, with trace_id)
    - Auto-advance to next mission
    """

    _ACTIVE_STATES: set[QueueItemState] = {
        QueueItemState.QUEUED,
        QueueItemState.READY,
        QueueItemState.LEASED,
        QueueItemState.RUNNING,
        QueueItemState.WAITING_APPROVAL,
        QueueItemState.RECOVERING,
        QueueItemState.VERIFYING,
        QueueItemState.EVIDENCE_PENDING,
    }

    # Failure classes that are retryable
    _RETRYABLE_FAILURES: set[str] = {
        "worker_failure", "lease_expired", "code_failure",
        "test_failure", "environment_failure", "external_service_failure",
    }

    def __init__(
        self, store: SQLiteStore, events: EventBus, evidence: EvidenceStore,
        orchestrator: RuntimeOrchestrator | None = None,
        permission_broker: PermissionBroker | None = None,
        recovery_engine: RecoveryEngine | None = None,
        cost_optimizer: CostOptimizer | None = None,
        health_monitor: HealthMonitor | None = None,
        execution_gateway: ExecutionGateway | None = None,
        config: SupervisorConfig | None = None,
    ) -> None:
        self._store = store
        self._events = events
        self._evidence = evidence
        self.orchestrator = orchestrator or RuntimeOrchestrator(store, events, evidence)
        self.permissions = permission_broker or PermissionBroker()
        self.recovery = recovery_engine or RecoveryEngine()
        self.cost = cost_optimizer or CostOptimizer()
        self.health = health_monitor or HealthMonitor()
        self.gateway = execution_gateway or ExecutionGateway(permission_broker=self.permissions)
        self.config = config or SupervisorConfig()

        # Wire PermissionBroker into the gateway
        self.gateway.permissions = self.permissions

        self._state = SupervisorState.IDLE
        self._current_mission_id: str | None = None
        self._mission_history: list[dict[str, Any]] = []
        self._active = False
        self._stop_flag = threading.Event()
        self._started_at: float | None = None

        self._completed_evidence_written: set[str] = set()
        self._consecutive_errors: int = 0

    # ── lifecycle ──

    def start(self, block: bool = False) -> None:
        self._active = True
        self._stop_flag.clear()
        self._started_at = time.time()
        if block:
            self._run()
        else:
            t = threading.Thread(target=self._run, daemon=True, name="nexara-supervisor")
            t.start()

    def stop(self) -> None:
        self._active = False
        self._stop_flag.set()

    @property
    def state(self) -> SupervisorState:
        return self._state

    @property
    def current_mission_id(self) -> str | None:
        return self._current_mission_id

    # ── main loop ──

    def _run(self) -> None:
        while self._active and not self._stop_flag.is_set():
            try:
                self._execute_supervisor_cycle()
                self._consecutive_errors = 0
            except Exception as exc:
                self._consecutive_errors += 1
                self._record_cycle_error(exc)
                if self._consecutive_errors >= self.config.max_consecutive_errors:
                    self._state = SupervisorState.BLOCKED
                    self._emit_blocked_event(exc)
            self._stop_flag.wait(self.config.cycle_delay_s)

    def _execute_supervisor_cycle(self) -> None:
        self._state = SupervisorState.PLANNING

        status = self.orchestrator.status()
        has_active_work = (
            status.total_queued > 0
            or status.total_running > 0
            or self._has_pending_items()
        )

        if has_active_work:
            self._state = SupervisorState.DISPATCHING
            self._process_queued()
            self._dispatch_ready()
            self._recover_stale_leases()
            self._expire_stale_approvals()

        self._check_completions()
        self._state = SupervisorState.MONITORING
        self.health.check_all()

    def _has_pending_items(self) -> bool:
        for state in self._ACTIVE_STATES:
            items = self.orchestrator.mission_queue.list_by_state(state)
            if items:
                return True
        return False

    # ── dispatching ──

    def _process_queued(self) -> None:
        """Move queued items to ready if dependencies are met AND available_at is reached.

        Errors propagate to _run() for structured handling.
        """
        queued = self.orchestrator.mission_queue.list_by_state(QueueItemState.QUEUED)
        for item in queued:
            # Respect available_at scheduling — future missions stay QUEUED
            if not self._is_available_now(item):
                continue
            if self._dependencies_satisfied(item):
                self.orchestrator.mission_queue.transition(
                    item.mission_id, QueueItemState.READY
                )

    @staticmethod
    def _is_available_now(item: MissionQueueItem) -> bool:
        """True if available_at is None or has passed."""
        if item.available_at is None:
            return True
        now = datetime.now(timezone.utc)
        try:
            avail = datetime.fromisoformat(item.available_at)
            return avail <= now
        except (ValueError, TypeError):
            return True  # unparseable → assume available

    def _dispatch_ready(self) -> None:
        """Dispatch ready missions through the execution gateway.

        - Respects max_concurrent_missions: started + new <= configured max
        - Auto-selects worker if preferred_worker is None
        - Persists lease fields BEFORE transitioning to RUNNING
        - Passes full mission payload (command, prompt, cwd, capabilities,
          run_id, trace_id) to the worker — NOT just mission_id + priority
        - Rejects missions with empty command AND empty prompt
        - Hands off to Worker for execution; completion goes through
          RuntimeOrchestrator.complete_mission() with Evidence completion gate
        - Handles WorkerResult: success→complete_mission, retryable→recover,
          fatal→BLOCKED
        """
        ready = self.orchestrator.mission_queue.list_by_state(QueueItemState.READY)
        if not ready:
            return

        # Count currently running missions for max_concurrent enforcement
        running = self.orchestrator.mission_queue.list_by_state(QueueItemState.RUNNING)
        leased = self.orchestrator.mission_queue.list_by_state(QueueItemState.LEASED)
        current_running = len(running) + len(leased)

        for item in ready:
            # ── Thread 12: max_concurrent_missions enforcement ──
            if current_running >= self.config.max_concurrent_missions:
                break  # Leave remaining items in READY; will retry next cycle

            # ── Thread 11: Respect available_at (double-check after promotion) ──
            if not self._is_available_now(item):
                continue

            # Auto-select worker if none pinned
            worker_id = item.preferred_worker
            if not worker_id:
                scheduled = self.orchestrator.worker_scheduler.schedule(item)
                if scheduled is None:
                    # No suitable worker — leave in READY, will retry next cycle
                    continue
                worker_id = scheduled.worker_id

            # ── Thread 8: Build full mission payload ──
            full_mission = self._build_mission_payload(item)
            command = full_mission.get("command", "")
            prompt = full_mission.get("prompt", "")

            # Reject empty payloads — cannot produce fake completion
            if not command and not prompt:
                self.orchestrator.mission_queue.transition(
                    item.mission_id, QueueItemState.BLOCKED,
                )
                self._record_evidence(item.mission_id, "mission_blocked", {
                    "mission_id": item.mission_id,
                    "reason": "empty command and prompt — cannot execute",
                })
                continue

            # ── Thread 9: Persist lease fields BEFORE RUNNING transition ──
            lease_expires_ts = (
                datetime.now(timezone.utc).timestamp()
                + self.config.default_lease_duration_s
            )
            lease_expires_str = datetime.fromtimestamp(
                lease_expires_ts, tz=timezone.utc
            ).isoformat()
            item.attempt_count += 1

            # Persist via transition with extra fields
            self.orchestrator.mission_queue.transition(
                item.mission_id, QueueItemState.RUNNING,
                lease_owner=worker_id,
                lease_expires_at=lease_expires_str,
                attempt_count=item.attempt_count,
            )

            # ── Dispatch through gateway (PermissionBroker enforced inside) ──
            result = self.gateway.dispatch(
                worker_id, item.mission_id, full_mission,
            )

            # ── Thread 10: Handle result through complete_mission / recovery ──
            if result.success:
                self.orchestrator.complete_mission(
                    item.mission_id, worker_id, worker_result=result,
                )
            elif result.failure_class and result.failure_class.value in self._RETRYABLE_FAILURES:
                self._handle_retryable_failure(item, result)
            else:
                self.orchestrator.mission_queue.transition(
                    item.mission_id, QueueItemState.BLOCKED,
                )
                self._record_evidence(item.mission_id, "mission_blocked", {
                    "mission_id": item.mission_id,
                    "reason": str(result.output.get("error", "non-retryable failure")),
                    "failure_class": result.failure_class.value if result.failure_class else "unknown",
                })

            current_running += 1

    def _build_mission_payload(self, item: MissionQueueItem) -> dict[str, Any]:
        """Build the full mission payload from a queue item.

        Includes command, prompt, cwd, capabilities, run_id, trace_id.
        This is the REAL mission payload passed to the Worker — not just
        mission_id and priority.
        """
        from ..models import Mission

        payload: dict[str, Any] = {
            "mission_id": item.mission_id,
            "priority": item.priority,
            "trace_id": f"sv:{item.mission_id}:{_utc_now()}",
            "run_id": f"run:{item.mission_id}:{item.attempt_count}",
        }

        # Try mission_payload record first (set by submit_mission with command/prompt)
        try:
            mp_raw = self._store.find_record(
                "mission_payload", "mission_id", item.mission_id,
            )
            if mp_raw:
                p = mp_raw.get("payload", mp_raw)
                payload["command"] = p.get("command", "")
                payload["prompt"] = p.get("prompt", "")
                payload["cwd"] = p.get("cwd", "")
                payload["capabilities"] = p.get("capabilities", [])
                return payload
        except Exception:
            pass

        # Fall back to full Mission record
        try:
            raw = self._store.get_record(item.mission_id)
            if raw:
                mission = Mission.model_validate(raw)
                payload["command"] = mission.spec.objective or ""
                payload["cwd"] = mission.spec.source_dir or ""
                payload["capabilities"] = [
                    a.loaded_capabilities for a in (mission.assignments or [])
                ]
                payload["trace_id"] = mission.trace_id
        except (KeyError, Exception):
            pass

        # Ensure required fields are populated
        payload.setdefault("command", "")
        payload.setdefault("prompt", "")
        payload.setdefault("cwd", "")
        payload.setdefault("capabilities", item.required_capabilities or [])

        return payload

    def _handle_retryable_failure(
        self, item: MissionQueueItem, result: Any,
    ) -> None:
        """Route retryable failure through RecoveryEngine."""
        recovery_result = self.recovery.recover(
            item.mission_id,
            result.failure_class.value if result.failure_class else "unknown",
            attempt=item.attempt_count,
            last_error=str(result.output.get("error", "")),
        )
        if recovery_result.success and recovery_result.strategy != RecoveryStrategy.ESCALATE:
            self.orchestrator.mission_queue.transition(
                item.mission_id, QueueItemState.RECOVERING
            )
            # Re-queue for retry
            self.orchestrator.mission_queue.transition(
                item.mission_id, QueueItemState.QUEUED
            )
        else:
            self.orchestrator.mission_queue.transition(
                item.mission_id, QueueItemState.BLOCKED
            )

    # ── stale lease recovery ──

    def _recover_stale_leases(self) -> None:
        """Recover missions with stale leases. Processes recovery result."""
        now = time.time()
        for state in (QueueItemState.LEASED, QueueItemState.RUNNING):
            items = self.orchestrator.mission_queue.list_by_state(state)
            for item in items:
                if not item.lease_expires_at:
                    continue
                try:
                    expires = datetime.fromisoformat(item.lease_expires_at)
                    if (now - expires.timestamp()) <= self.config.stale_lease_timeout_s:
                        continue
                except (ValueError, OSError):
                    continue

                self.orchestrator.mission_queue.transition(
                    item.mission_id, QueueItemState.RECOVERING
                )
                recovery_result = self.recovery.recover(
                    item.mission_id, "stale_lease",
                    attempt=item.attempt_count + 1,
                    last_error="lease expired",
                )

                # Process recovery result
                if recovery_result.success and recovery_result.strategy != RecoveryStrategy.ESCALATE:
                    # Retryable — requeue
                    self.orchestrator.mission_queue.transition(
                        item.mission_id, QueueItemState.QUEUED
                    )
                else:
                    # Exhausted or escalated — BLOCKED
                    self.orchestrator.mission_queue.transition(
                        item.mission_id, QueueItemState.BLOCKED
                    )
                    self._record_evidence(item.mission_id, "stale_lease_exhausted", {
                        "mission_id": item.mission_id,
                        "attempt": item.attempt_count + 1,
                        "strategy": recovery_result.strategy.value,
                    })

    def _expire_stale_approvals(self) -> None:
        """Expire approvals that have timed out."""
        waiting = self.orchestrator.mission_queue.list_by_state(
            QueueItemState.WAITING_APPROVAL
        )
        now = time.time()
        for item in waiting:
            if not item.updated_at:
                continue
            try:
                updated = datetime.fromisoformat(item.updated_at)
                if (now - updated.timestamp()) <= self.config.approval_expiry_timeout_s:
                    continue
            except (ValueError, OSError):
                continue

            self.orchestrator.mission_queue.transition(
                item.mission_id, QueueItemState.BLOCKED
            )
            self._record_evidence(item.mission_id, "approval_expired", {
                "mission_id": item.mission_id,
                "reason": "approval timeout",
            })

    def _dependencies_satisfied(self, item: MissionQueueItem) -> bool:
        if not item.dependencies:
            return True
        for dep_id in item.dependencies:
            dep = self.orchestrator.mission_queue.get(dep_id)
            if dep is None or dep.state != QueueItemState.COMPLETED:
                return False
        return True

    # ── completions ──

    def _check_completions(self) -> None:
        completed = self.orchestrator.mission_queue.list_by_state(QueueItemState.COMPLETED)
        for item in completed:
            self._on_mission_complete(item)

    def _on_mission_complete(self, item: MissionQueueItem) -> None:
        """Record completion evidence — idempotent per mission_id + state.

        Uses BOTH an in-memory set AND a persistent EvidenceStore query
        to guarantee idempotency across restarts. The in-memory set is
        a fast-path optimization; the persistent store is the source of
        truth for crash-restart scenarios.
        """
        evidence_key = f"{item.mission_id}:{item.state.value}:completed"
        if evidence_key in self._completed_evidence_written:
            return

        # ── Thread 13: Persistent idempotency check ──
        existing = self._evidence.list(mission_id=item.mission_id)
        for e in existing:
            if (
                e.get("kind") == "mission_completed"
                and e.get("mission_id") == item.mission_id
            ):
                # Already persisted — skip but cache the fact in memory
                self._completed_evidence_written.add(evidence_key)
                return

        self._mission_history.append({
            "mission_id": item.mission_id, "completed_at": _utc_now(),
            "state": item.state.value,
        })
        if self.config.evidence_on_completion:
            self._record_evidence(
                item.mission_id, "mission_completed",
                {
                    "mission_id": item.mission_id,
                    "state": item.state.value,
                },
                idempotency_key=f"completion:{item.mission_id}:{item.state.value}",
            )
        self._completed_evidence_written.add(evidence_key)

    # ── mission management ──

    def submit_mission(self, mission_id: str, priority: int = 0,
                       capabilities: list[str] | None = None,
                       risk: RiskLevel = RiskLevel.R1,
                       command: str = "", prompt: str = "",
                       cwd: str = "",
                       available_at: str | None = None,
                       idempotency_key: str | None = None,
                       dependencies: list[str] | None = None,
                       max_attempts: int = 3) -> MissionQueueItem:
        item = MissionQueueItem(
            mission_id=mission_id, priority=priority,
            state=QueueItemState.QUEUED, risk_level=risk,
            required_capabilities=capabilities or [],
            available_at=available_at,
            idempotency_key=idempotency_key,
            dependencies=dependencies or [],
            max_attempts=max_attempts,
        )
        self.orchestrator.mission_queue.enqueue(item)
        self._current_mission_id = mission_id

        # Persist mission metadata (command, prompt, cwd) as a record so
        # _build_mission_payload can retrieve it even without a full Mission
        if command or prompt:
            self._store.save_record(
                f"payload:{mission_id}", "mission_payload",
                {"mission_id": mission_id, "command": command,
                 "prompt": prompt, "cwd": cwd,
                 "capabilities": capabilities or []},
                created_at=_utc_now(), mission_id=mission_id,
            )

        return item

    def mission_status(self, mission_id: str) -> dict[str, Any]:
        item = self.orchestrator.mission_queue.get(mission_id)
        if item is None:
            return {"mission_id": mission_id, "status": "not_found"}
        return {
            "mission_id": item.mission_id, "state": item.state.value,
            "priority": item.priority, "attempt_count": item.attempt_count,
            "risk_level": item.risk_level.value if item.risk_level else "R1",
        }

    # ── evidence ──

    def _record_evidence(
        self, mission_id: str, kind: str, content: dict[str, Any],
        trace_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        tid = trace_id or f"sv:{mission_id}:{kind}:{_utc_now()}"
        try:
            self._evidence.add(
                mission_id=mission_id, kind=kind,
                title=f"{kind}: {mission_id}",
                content=json.dumps(content, default=str),
                trace_id=tid,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:
            self._events.publish(
                event_type="evidence_write_failure",
                aggregate_id=mission_id,
                aggregate_type="mission",
                actor="supervisor",
                trace_id=tid,
                payload={"mission_id": mission_id, "kind": kind, "error": str(exc)},
            )

    def _record_cycle_error(self, exc: Exception) -> None:
        """Record a structured cycle error to EventBus and Evidence."""
        tid = f"sv:cycle_error:{_utc_now()}"
        error_info = {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "error_hash": hashlib.sha256(
                f"{type(exc).__name__}:{str(exc)}".encode()
            ).hexdigest()[:16],
            "stack_trace": traceback.format_exc()[-2000:],
            "consecutive_errors": self._consecutive_errors,
            "timestamp": _utc_now(),
        }
        self._events.publish(
            event_type="supervisor_cycle_error",
            aggregate_id="supervisor",
            aggregate_type="supervisor",
            actor="supervisor",
            trace_id=tid,
            payload=error_info,
        )
        try:
            self._evidence.add(
                mission_id="supervisor", kind="cycle_error",
                title=f"Supervisor cycle error: {type(exc).__name__}",
                content=json.dumps(error_info, default=str),
                trace_id=tid,
            )
        except Exception:
            pass

    def _emit_blocked_event(self, exc: Exception) -> None:
        tid = f"sv:blocked:{_utc_now()}"
        self._events.publish(
            event_type="supervisor_blocked",
            aggregate_id="supervisor",
            aggregate_type="supervisor",
            actor="supervisor",
            trace_id=tid,
            payload={
                "reason": f"max consecutive errors ({self.config.max_consecutive_errors})",
                "last_error": str(exc),
                "timestamp": _utc_now(),
            },
        )

    # ── status ──

    def status_report(self) -> dict[str, Any]:
        orch_status = self.orchestrator.status()
        return {
            "supervisor_state": self._state.value,
            "current_mission_id": self._current_mission_id,
            "orchestrator": {
                "queued": orch_status.total_queued, "running": orch_status.total_running,
                "blocked": orch_status.total_blocked, "completed": orch_status.total_completed,
                "pending_approvals": orch_status.pending_approvals,
            },
            "permissions": self.permissions.to_evidence(),
            "recovery": self.recovery.to_evidence(),
            "cost": self.cost.to_evidence(),
            "health": self.health.to_evidence(),
            "gateway": self.gateway.to_evidence(),
            "uptime_s": time.time() - (self._started_at or time.time()),
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
