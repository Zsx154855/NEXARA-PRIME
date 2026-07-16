"""Worker health monitoring — heartbeat, dead detection, status tracking."""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any


class WorkerStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNRESPONSIVE = "unresponsive"
    DEAD = "dead"
    UNKNOWN = "unknown"


@dataclass
class WorkerHealth:
    worker_id: str
    status: WorkerStatus
    last_heartbeat: float = 0.0
    last_error: str = ""
    error_count: int = 0
    task_count: int = 0
    uptime_s: float = 0.0


class HealthMonitor:
    """Monitors worker health via heartbeat and failure tracking."""

    HEARTBEAT_TIMEOUT_S = 120.0
    DEAD_TIMEOUT_S = 300.0

    def __init__(self) -> None:
        self._workers: dict[str, WorkerHealth] = {}
        self._started_at = time.time()

    def register(self, worker_id: str) -> WorkerHealth:
        h = WorkerHealth(
            worker_id=worker_id, status=WorkerStatus.UNKNOWN,
            last_heartbeat=time.time(), uptime_s=0.0,
        )
        self._workers[worker_id] = h
        return h

    def heartbeat(self, worker_id: str) -> WorkerHealth:
        h = self._workers.get(worker_id)
        if h is None:
            h = self.register(worker_id)
        h.last_heartbeat = time.time()
        h.status = WorkerStatus.HEALTHY
        h.uptime_s = time.time() - self._started_at
        return h

    def record_error(self, worker_id: str, error: str) -> None:
        h = self._workers.get(worker_id)
        if h is None:
            h = self.register(worker_id)
        h.error_count += 1
        h.last_error = error
        if h.error_count >= 3:
            h.status = WorkerStatus.DEGRADED

    def record_task(self, worker_id: str) -> None:
        h = self._workers.get(worker_id)
        if h:
            h.task_count += 1

    def check_all(self) -> list[WorkerHealth]:
        now = time.time()
        results = []
        for h in self._workers.values():
            since_heartbeat = now - h.last_heartbeat
            if since_heartbeat > self.DEAD_TIMEOUT_S:
                h.status = WorkerStatus.DEAD
            elif since_heartbeat > self.HEARTBEAT_TIMEOUT_S:
                h.status = WorkerStatus.UNRESPONSIVE
            results.append(h)
        return results

    def get(self, worker_id: str) -> WorkerHealth | None:
        return self._workers.get(worker_id)

    def get_alive_workers(self) -> list[str]:
        self.check_all()
        return [
            wid for wid, h in self._workers.items()
            if h.status in (WorkerStatus.HEALTHY, WorkerStatus.DEGRADED)
        ]

    def to_evidence(self) -> dict[str, Any]:
        self.check_all()
        return {
            "workers": {
                wid: {"status": h.status.value, "errors": h.error_count, "tasks": h.task_count}
                for wid, h in self._workers.items()
            },
            "alive_count": len(self.get_alive_workers()),
        }
