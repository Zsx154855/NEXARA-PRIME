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
from ..models import ApprovalRequest, ApprovalStatus
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
            self._reconcile_approvals()
            self._process_queued()
            self._dispatch_ready()
            self._retry_evidence_pending()
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

    def _reconcile_approvals(self) -> None:
        """Thread A: Reconcile WAITING_APPROVAL missions against ApprovalQueue.

        - approved/consumed → promote to READY (preserving action context)
        - rejected → immediate BLOCKED (don't wait for expiry timeout)
        - expired → immediate BLOCKED
        - still pending → unchanged
        """
        waiting = self.orchestrator.mission_queue.list_by_state(
            QueueItemState.WAITING_APPROVAL,
        )
        for item in waiting:
            approval_status = self._get_approval_status(item.mission_id)
            if approval_status is None:
                continue  # No approval record — leave as is

            if approval_status == ApprovalStatus.CONSUMED.value:
                self.orchestrator.mission_queue.transition(
                    item.mission_id, QueueItemState.READY,
                )
                self._record_evidence(item.mission_id, "approval_consumed_resume", {
                    "mission_id": item.mission_id,
                    "action": "consumed approval → READY for dispatch",
                })
            elif approval_status == ApprovalStatus.REJECTED.value:
                self.orchestrator.mission_queue.transition(
                    item.mission_id, QueueItemState.BLOCKED,
                )
                self._record_evidence(item.mission_id, "approval_rejected_blocked", {
                    "mission_id": item.mission_id,
                    "reason": "approval explicitly rejected — immediate BLOCKED",
                })
                # Release any writer lease that may exist
                self.orchestrator.leases.release(item.mission_id,
                    item.lease_owner or "unknown")
            elif approval_status == ApprovalStatus.EXPIRED.value:
                self.orchestrator.mission_queue.transition(
                    item.mission_id, QueueItemState.BLOCKED,
                )
                self._record_evidence(item.mission_id, "approval_expired_blocked", {
                    "mission_id": item.mission_id,
                    "reason": "approval expired — immediate BLOCKED",
                })

    def _get_approval_status(self, mission_id: str) -> str | None:
        """Return the latest approval status for a mission, or None if no record."""
        latest_status: str | None = None
        latest_created: str = ""
        for raw in self._store.list_records("approval_requests"):
            p = raw.get("payload", raw)
            if p.get("mission_id") != mission_id:
                continue
            created = p.get("created_at", "")
            if created > latest_created:
                latest_created = created
                latest_status = p.get("status")
        return latest_status

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
        """True if available_at is None or has passed.

        Naive ISO timestamps (without timezone) are treated as UTC,
        matching the existing orchestrator parser behaviour.
        """
        if item.available_at is None:
            return True
        now = datetime.now(timezone.utc)
        try:
            avail = datetime.fromisoformat(item.available_at)
            # Treat naive datetimes as UTC for consistent comparison
            if avail.tzinfo is None:
                avail = avail.replace(tzinfo=timezone.utc)
            return avail <= now
        except (ValueError, TypeError):
            return True  # unparseable → assume available

    def _dispatch_ready(self) -> None:
        """Dispatch ready missions through the execution gateway.

        - Sorts READY by priority desc, created_at asc (preserves priority)
        - Respects max_concurrent_missions
        - Validates preferred_worker through scheduler (health, capability,
          availability, writer predicates)
        - Passes full mission payload (command, prompt, cwd, capabilities)
        - Blocks prompt-only missions from LocalShellWorker
        - Routes escalations into ApprovalQueue + WAITING_APPROVAL
        - Persists lease fields BEFORE transitioning to RUNNING
        - Hands off to RuntimeOrchestrator.complete_mission() (evidence gate)
        - Handles WorkerResult: success→complete, evidence-pending→EVIDENCE_PENDING,
          retryable→recover, fatal→BLOCKED
        - Enforces mission.max_attempts on retry/recovery
        """
        ready = self.orchestrator.mission_queue.list_by_state(QueueItemState.READY)
        if not ready:
            return

        # ── Thread 41: Sort by priority desc, created_at asc ──
        ready.sort(key=lambda i: (-i.priority, i.created_at))

        # Count currently running missions for max_concurrent enforcement
        running = self.orchestrator.mission_queue.list_by_state(QueueItemState.RUNNING)
        leased = self.orchestrator.mission_queue.list_by_state(QueueItemState.LEASED)
        current_running = len(running) + len(leased)

        for item in ready:
            # ── Thread 12: max_concurrent_missions enforcement ──
            if current_running >= self.config.max_concurrent_missions:
                break

            # ── Thread 11: Respect available_at ──
            if not self._is_available_now(item):
                continue

            # Build full mission payload
            full_mission = self._build_mission_payload(item)
            command = full_mission.get("command", "")
            prompt = full_mission.get("prompt", "")

            # ── Reject empty payloads ──
            if not command and not prompt:
                self.orchestrator.mission_queue.transition(
                    item.mission_id, QueueItemState.BLOCKED,
                )
                self._record_evidence(item.mission_id, "mission_blocked", {
                    "mission_id": item.mission_id,
                    "reason": "empty command and prompt — cannot execute",
                })
                continue

            # ── Thread 42: Validate preferred worker through scheduler ──
            worker_id = item.preferred_worker
            if worker_id:
                # Even when preferred_worker is set, validate through scheduler
                scheduled = self.orchestrator.worker_scheduler.schedule(item)
                if scheduled is None or scheduled.worker_id != worker_id:
                    # Preferred worker is incompatible — block, don't guess
                    self.orchestrator.mission_queue.transition(
                        item.mission_id, QueueItemState.BLOCKED,
                    )
                    self._record_evidence(item.mission_id, "mission_blocked", {
                        "mission_id": item.mission_id,
                        "reason": f"preferred worker '{worker_id}' incompatible or unavailable",
                    })
                    continue
                # Worker is compatible — use it
            else:
                # Auto-select worker via scheduler
                scheduled = self.orchestrator.worker_scheduler.schedule(item)
                if scheduled is None:
                    continue  # No suitable worker — leave in READY
                worker_id = scheduled.worker_id

            # ── Thread V6-E: Symmetric worker compatibility ──
            worker = self.orchestrator.worker_scheduler.get(worker_id)
            if worker:
                worker_type = worker.worker_type.value
                is_llm = worker_type in ("claude", "code_reviewer")
                is_shell = worker_type == "local_tool"
                has_command = bool(command)
                has_prompt = bool(prompt)

                # Command-only → must go to command-capable worker (shell)
                if has_command and not has_prompt and is_llm:
                    self.orchestrator.mission_queue.transition(
                        item.mission_id, QueueItemState.BLOCKED,
                    )
                    self._record_evidence(item.mission_id, "mission_blocked", {
                        "mission_id": item.mission_id,
                        "reason": f"command-only mission cannot execute on LLM worker '{worker_id}' — use a shell worker",
                    })
                    continue

                # Prompt-only → must go to prompt-capable worker (LLM)
                if has_prompt and not has_command and is_shell:
                    self.orchestrator.mission_queue.transition(
                        item.mission_id, QueueItemState.BLOCKED,
                    )
                    self._record_evidence(item.mission_id, "mission_blocked", {
                        "mission_id": item.mission_id,
                        "reason": "prompt-only mission cannot execute on LocalShellWorker",
                    })
                    continue

            # ── Thread 43: Enforce max_attempts ──
            if item.attempt_count >= item.max_attempts:
                self.orchestrator.mission_queue.transition(
                    item.mission_id, QueueItemState.BLOCKED,
                )
                self._record_evidence(item.mission_id, "mission_blocked", {
                    "mission_id": item.mission_id,
                    "reason": f"max_attempts ({item.max_attempts}) reached",
                    "attempt_count": item.attempt_count,
                })
                continue

            # ── Thread V6-B: Acquire durable writer lease BEFORE dispatch ──
            if not self.orchestrator.leases.acquire(item.mission_id, worker_id):
                # Another supervisor/worker holds the lease — leave READY
                continue

            # ── Thread V6-H: Check for single-use consumed approval ──
            approved_command = self._get_and_consume_approval(item.mission_id)

            # Thread V6-F: attempt_count only incremented when REAL dispatch starts
            item.attempt_count += 1

            # Persist lease fields BEFORE transitioning to RUNNING
            lease_expires_ts = (
                datetime.now(timezone.utc).timestamp()
                + self.config.default_lease_duration_s
            )
            lease_expires_str = datetime.fromtimestamp(
                lease_expires_ts, tz=timezone.utc
            ).isoformat()

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
                approved_command=approved_command,
            )

            # ── Thread 34: Route escalations into ApprovalQueue ──
            if (
                not result.success
                and result.failure_class
                and result.failure_class.value == "permission_block"
                and result.output.get("escalated")
            ):
                # Thread V6-F: escalation is NOT an execution attempt — revert
                # and persist the reverted count on the WAITING_APPROVAL transition
                reverted_attempt = item.attempt_count - 1
                # Release the durable lease — we are not executing
                self.orchestrator.leases.release(item.mission_id, worker_id)
                self._create_approval_for_escalation(item, result, worker_id)
                self.orchestrator.mission_queue.transition(
                    item.mission_id, QueueItemState.WAITING_APPROVAL,
                    attempt_count=reverted_attempt,
                )
                self._record_evidence(item.mission_id, "mission_awaiting_approval", {
                    "mission_id": item.mission_id,
                    "command": command,
                    "worker_id": worker_id,
                    "decision_id": result.output.get("decision_id"),
                })
                current_running += 1
                continue

            # ── Thread 10: Handle result through complete_mission / recovery ──
            if result.success:
                completed = self.orchestrator.complete_mission(
                    item.mission_id, worker_id, worker_result=result,
                )
                if not completed:
                    # ── Thread 37: Evidence gate not yet passed ──
                    self._persist_worker_result(item.mission_id, result)
                    self.orchestrator.mission_queue.transition(
                        item.mission_id, QueueItemState.EVIDENCE_PENDING,
                    )
                    self._record_evidence(item.mission_id, "evidence_pending", {
                        "mission_id": item.mission_id,
                        "worker_id": worker_id,
                        "worker_success": True,
                    })
            elif (
                result.failure_class
                and result.failure_class.value in self._RETRYABLE_FAILURES
                and item.attempt_count < item.max_attempts
            ):
                self.orchestrator.leases.release(item.mission_id, worker_id)
                self._handle_retryable_failure(item, result)
            else:
                self.orchestrator.leases.release(item.mission_id, worker_id)
                self.orchestrator.mission_queue.transition(
                    item.mission_id, QueueItemState.BLOCKED,
                )
                reason = str(result.output.get("error", "non-retryable failure"))
                self._record_evidence(item.mission_id, "mission_blocked", {
                    "mission_id": item.mission_id,
                    "reason": reason,
                    "failure_class": (
                        result.failure_class.value
                        if result.failure_class else "unknown"
                    ),
                })

            current_running += 1

    def _build_mission_payload(self, item: MissionQueueItem) -> dict[str, Any]:
        """Build the full mission payload from a queue item.

        Thread 45: Natural-language mission objectives (Mission.spec.objective)
        go into prompt, NEVER into command. Only explicit commands go into command.
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
                # Thread 45: Mission.spec.objective is a prompt, not a command
                objective = mission.spec.objective or ""
                payload["prompt"] = objective
                payload["command"] = ""
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

    def _retry_evidence_pending(self) -> None:
        """Retry completing EVIDENCE_PENDING missions.

        Thread V6-J: Distinguishes between:
        - Evidence PENDING: retry complete_mission() each cycle
        - Evidence FAILED: route to RecoveryEngine → retryable (regenerate) or BLOCKED

        Looping forever on permanently-failed evidence is not allowed.
        """
        pending = self.orchestrator.mission_queue.list_by_state(
            QueueItemState.EVIDENCE_PENDING,
        )
        for item in pending:
            worker_id = item.lease_owner or "unknown"

            # ── Thread V6-J: Check for FAILED evidence jobs ──
            failed_jobs = self.orchestrator.evidence_queue.failed_for_mission(
                item.mission_id,
            )
            if failed_jobs:
                # Permanent evidence failure — route through RecoveryEngine
                recovery_result = self.recovery.recover(
                    item.mission_id, "evidence_failure",
                    attempt=item.attempt_count,
                    last_error=f"{len(failed_jobs)} failed evidence job(s)",
                )
                if (
                    recovery_result.success
                    and recovery_result.strategy != RecoveryStrategy.ESCALATE
                ):
                    # Regenerate evidence then retry
                    self.orchestrator.mission_queue.transition(
                        item.mission_id, QueueItemState.RECOVERING,
                    )
                    self.orchestrator.mission_queue.transition(
                        item.mission_id, QueueItemState.QUEUED,
                    )
                else:
                    self.orchestrator.mission_queue.transition(
                        item.mission_id, QueueItemState.BLOCKED,
                    )
                    self._record_evidence(item.mission_id,
                        "evidence_gate_failed", {
                            "mission_id": item.mission_id,
                            "failed_jobs": len(failed_jobs),
                            "reason": "permanent evidence failure — BLOCKED",
                        })
                    self._events.publish(
                        event_type="evidence_gate_failed",
                        aggregate_id=item.mission_id,
                        aggregate_type="mission",
                        actor="supervisor",
                        trace_id=f"sv:{item.mission_id}:evidence_failed:{_utc_now()}",
                        payload={"mission_id": item.mission_id,
                                 "failed_jobs": len(failed_jobs)},
                    )
                continue

            # ── Evidence still pending (no failed jobs) — retry completion ──
            try:
                wr_raw = self._store.find_record(
                    "worker_result", "mission_id", item.mission_id,
                )
                if not wr_raw:
                    continue
                from ..models import WorkerResult as WR
                p = wr_raw.get("payload", wr_raw)
                wr_fields = {"worker_id", "mission_id", "success",
                             "failure_class", "output", "artifacts",
                             "evidence_refs", "token_usage", "duration_ms",
                             "next_action", "created_at"}
                filtered = {k: v for k, v in p.items() if k in wr_fields}
                worker_result = WR(**filtered)
                item.state = QueueItemState.RUNNING
                self.orchestrator.mission_queue.transition(
                    item.mission_id, QueueItemState.RUNNING,
                )
                completed = self.orchestrator.complete_mission(
                    item.mission_id, worker_id, worker_result=worker_result,
                )
                if completed:
                    self._record_evidence(item.mission_id, "mission_completed", {
                        "mission_id": item.mission_id,
                        "from_evidence_pending": True,
                    })
                else:
                    # Still pending — move back
                    self.orchestrator.mission_queue.transition(
                        item.mission_id, QueueItemState.EVIDENCE_PENDING,
                    )
            except Exception:
                pass  # Will retry next cycle

    def _handle_retryable_failure(
        self, item: MissionQueueItem, result: Any,
    ) -> None:
        """Route retryable failure through RecoveryEngine.

        Enforces mission.max_attempts — after reaching the cap, transitions
        to BLOCKED regardless of recovery strategy.
        """
        # ── Thread 43: max_attempts check before retry ──
        if item.attempt_count >= item.max_attempts:
            self.orchestrator.mission_queue.transition(
                item.mission_id, QueueItemState.BLOCKED,
            )
            self._record_evidence(item.mission_id, "mission_blocked", {
                "mission_id": item.mission_id,
                "reason": f"max_attempts ({item.max_attempts}) exhausted on retryable failure",
                "attempt_count": item.attempt_count,
            })
            return

        recovery_result = self.recovery.recover(
            item.mission_id,
            result.failure_class.value if result.failure_class else "unknown",
            attempt=item.attempt_count,
            last_error=str(result.output.get("error", "")),
        )
        if (
            recovery_result.success
            and recovery_result.strategy != RecoveryStrategy.ESCALATE
            and item.attempt_count < item.max_attempts
        ):
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
            self._record_evidence(item.mission_id, "mission_blocked", {
                "mission_id": item.mission_id,
                "reason": "recovery exhausted or max_attempts reached",
                "attempt_count": item.attempt_count,
            })

    # ── approval routing helpers ──

    def _create_approval_for_escalation(
        self, item: MissionQueueItem, result: Any, worker_id: str,
    ) -> None:
        """Create an ApprovalRequest and persist mission context for resume."""
        from datetime import datetime, timedelta, timezone as tz

        command = result.output.get("command", "")
        risk_level = result.output.get("risk_level", "R3")
        decision_id = result.output.get("decision_id", "")

        approval = ApprovalRequest(
            mission_id=item.mission_id,
            action=command,
            risk_level=RiskLevel(risk_level),
            rationale=f"Escalated command requires human approval: {command[:120]}",
            reason=result.output.get("reason", "R3/R4 escalation"),
            external_effect=True,
            reversible=False,
            executor_id=worker_id,
            expires_at=(
                datetime.now(tz.utc)
                + timedelta(seconds=self.config.approval_expiry_timeout_s)
            ).isoformat(),
            status=ApprovalStatus.PENDING,
        )
        self.orchestrator.approvals.create(approval)

        # Save the full dispatch context so it can be resumed after approval
        self._store.save_record(
            f"approval_ctx:{item.mission_id}", "approval_context",
            {
                "mission_id": item.mission_id,
                "command": command,
                "worker_id": worker_id,
                "decision_id": decision_id,
                "trace_id": f"sv:{item.mission_id}:{_utc_now()}",
            },
            created_at=_utc_now(),
            mission_id=item.mission_id,
        )

    def _get_and_consume_approval(self, mission_id: str) -> str | None:
        """Return the approved command if an unused consumed approval exists.

        Thread V6-H: Each consumed approval is a single-use grant. After the first
        real execution, the grant is marked 'grant_used=true' so retries, stale
        recoveries, and requeues cannot reuse the same approval. A changed action
        requires a fresh ApprovalRequest.
        """
        for raw in self._store.list_records("approval_requests"):
            p = raw.get("payload", raw)
            if p.get("mission_id") != mission_id:
                continue
            if p.get("status") != ApprovalStatus.CONSUMED.value:
                continue
            if p.get("grant_used"):
                continue  # Already used — single-use only
            # Mark grant as used BEFORE returning — races are benign
            # because writer lease ensures single dispatcher per mission
            p["grant_used"] = True
            p["grant_used_at"] = _utc_now()
            self._store.save_record(
                p.get("approval_id", f"approval:{mission_id}"),
                "approval_requests", p,
                created_at=p.get("created_at", _utc_now()),
                mission_id=mission_id,
            )
            return p.get("action", "")
        return None

    def _persist_worker_result(self, mission_id: str, result: Any) -> None:
        """Persist a successful WorkerResult so it can be used after evidence gate passes."""
        self._store.save_record(
            f"worker_result:{mission_id}", "worker_result",
            {
                "mission_id": mission_id,
                "worker_id": result.worker_id,
                "success": result.success,
                "output": result.output,
                "duration_ms": result.duration_ms,
                "failure_class": result.failure_class.value if result.failure_class else None,
                "persisted_at": _utc_now(),
            },
            created_at=_utc_now(),
            mission_id=mission_id,
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

                # Process recovery result — honour max_attempts
                # Thread V6-D: attempt_count already reflects dispatched attempts;
                # compare directly, don't add 1 (which would block one attempt early)
                if item.attempt_count >= item.max_attempts:
                    self.orchestrator.mission_queue.transition(
                        item.mission_id, QueueItemState.BLOCKED,
                    )
                    self._record_evidence(item.mission_id, "stale_lease_exhausted", {
                        "mission_id": item.mission_id,
                        "attempt": item.attempt_count,
                        "reason": f"max_attempts ({item.max_attempts}) reached on stale lease",
                    })
                elif (
                    recovery_result.success
                    and recovery_result.strategy != RecoveryStrategy.ESCALATE
                ):
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
                        "attempt": item.attempt_count,
                        "strategy": recovery_result.strategy.value,
                    })

    def _expire_stale_approvals(self) -> None:
        """Expire approvals that have timed out OR been rejected/expired.

        Thread V6-G: Also inspects ApprovalQueue status for rejected/expired
        approvals, not just time-based expiry. Rejected missions are terminated
        immediately without waiting for approval_expiry_timeout_s.
        """
        waiting = self.orchestrator.mission_queue.list_by_state(
            QueueItemState.WAITING_APPROVAL
        )
        now = time.time()
        for item in waiting:
            # ── Thread V6-G: Check approval status first ──
            approval_status = self._get_approval_status(item.mission_id)
            if approval_status in (ApprovalStatus.REJECTED.value,
                                    ApprovalStatus.EXPIRED.value):
                self.orchestrator.mission_queue.transition(
                    item.mission_id, QueueItemState.BLOCKED,
                )
                kind = ("approval_rejected_blocked" if approval_status == "rejected"
                       else "approval_expired_blocked")
                self._record_evidence(item.mission_id, kind, {
                    "mission_id": item.mission_id,
                    "reason": f"approval {approval_status} — immediate BLOCKED",
                })
                self.orchestrator.leases.release(item.mission_id,
                    item.lease_owner or "unknown")
                self._events.publish(
                    event_type=kind,
                    aggregate_id=item.mission_id,
                    aggregate_type="mission",
                    actor="supervisor",
                    trace_id=f"sv:{item.mission_id}:{kind}:{_utc_now()}",
                    payload={"mission_id": item.mission_id,
                             "approval_status": approval_status},
                )
                continue

            # ── Time-based expiry check ──
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
            self.orchestrator.leases.release(item.mission_id,
                item.lease_owner or "unknown")
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
