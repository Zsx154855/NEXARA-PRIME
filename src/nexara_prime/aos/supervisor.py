"""Autonomous Supervisor — plans, dispatches, monitors, and auto-advances missions."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..db import SQLiteStore
from ..events import EventBus
from ..evidence import EvidenceStore
from ..models import MissionQueueItem, QueueItemState, RiskLevel
from ..orchestration import RuntimeOrchestrator

from .permission_broker import PermissionBroker
from .recovery_engine import RecoveryEngine
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


class AutonomousSupervisor:
    """Top-level autonomous supervisor.

    Responsibilities:
    - Read current state from .nexara/*
    - Select next mission from the program loop
    - Dispatch to RuntimeOrchestrator
    - Monitor worker health and progress
    - Trigger recovery on failures
    - Write evidence on completion
    - Auto-advance to next mission
    """

    def __init__(
        self, store: SQLiteStore, events: EventBus, evidence: EvidenceStore,
        orchestrator: RuntimeOrchestrator | None = None,
        permission_broker: PermissionBroker | None = None,
        recovery_engine: RecoveryEngine | None = None,
        cost_optimizer: CostOptimizer | None = None,
        health_monitor: HealthMonitor | None = None,
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
        self.config = config or SupervisorConfig()

        self._state = SupervisorState.IDLE
        self._current_mission_id: str | None = None
        self._mission_history: list[dict[str, Any]] = []
        self._active = False
        self._stop_flag = threading.Event()
        self._started_at: float | None = None

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
            except Exception:
                pass
            self._stop_flag.wait(self.config.cycle_delay_s)

    def _execute_supervisor_cycle(self) -> None:
        self._state = SupervisorState.PLANNING
        # Check orchestrator for queued work
        if self.orchestrator.status().total_queued > 0:
            self._state = SupervisorState.DISPATCHING
            self.orchestrator._execute_cycle()
        # Check for completed missions needing evidence + advance
        self._check_completions()
        # Health check
        self._state = SupervisorState.MONITORING
        self.health.check_all()

    def _check_completions(self) -> None:
        completed = self.orchestrator.mission_queue.list_by_state(QueueItemState.COMPLETED)
        for item in completed:
            self._on_mission_complete(item)

    def _on_mission_complete(self, item: MissionQueueItem) -> None:
        self._mission_history.append({
            "mission_id": item.mission_id, "completed_at": _utc_now(),
            "state": item.state.value,
        })
        if self.config.evidence_on_completion:
            self._record_evidence(item.mission_id, "mission_completed", {
                "mission_id": item.mission_id, "state": item.state.value,
            })

    # ── mission management ──

    def submit_mission(self, mission_id: str, priority: int = 0,
                       capabilities: list[str] | None = None,
                       risk: RiskLevel = RiskLevel.R1) -> MissionQueueItem:
        item = MissionQueueItem(
            mission_id=mission_id, priority=priority,
            state=QueueItemState.QUEUED, risk_level=risk,
            required_capabilities=capabilities or [],
        )
        self.orchestrator.mission_queue.enqueue(item)
        self._current_mission_id = mission_id
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

    def _record_evidence(self, mission_id: str, kind: str, content: dict[str, Any]) -> None:
        try:
            self._evidence.add(
                mission_id=mission_id, kind=kind,
                title=f"{kind}: {mission_id}",
                content=json.dumps(content, default=str),
            )
        except Exception:
            pass

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
            "uptime_s": time.time() - (self._started_at or time.time()),
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
