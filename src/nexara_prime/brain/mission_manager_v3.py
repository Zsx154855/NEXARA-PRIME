"""Mission Manager V3 — autonomous mission lifecycle with queue, priority, resume, archive.

State machine: CREATED→QUEUED→PLANNED→APPROVED→EXECUTING→EVALUATING→COMPLETED→ARCHIVED
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexara_prime.models import now_iso, new_id


class MissionLifecycle(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    PLANNED = "planned"
    APPROVED = "approved"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class ManagedMission:
    mission_id: str
    objective: str
    risk_level: str = "R2"
    priority: int = 5
    status: MissionLifecycle = MissionLifecycle.CREATED
    created_at: str = field(default_factory=now_iso)
    resumed_count: int = 0
    meta: dict[str, Any] = field(default_factory=dict)


class MissionManagerV3:
    """Autonomous mission lifecycle manager with queue and priority."""

    def __init__(self) -> None:
        self._missions: dict[str, ManagedMission] = {}
        self._queue: list[str] = []

    def create(self, objective: str, risk_level: str = "R2", priority: int = 5) -> ManagedMission:
        mid = new_id("mis")
        m = ManagedMission(mid, objective, risk_level, priority, MissionLifecycle.CREATED)
        self._missions[mid] = m
        return m

    def enqueue(self, mission_id: str) -> ManagedMission | None:
        m = self._missions.get(mission_id)
        if m and m.status == MissionLifecycle.CREATED:
            m = ManagedMission(m.mission_id, m.objective, m.risk_level, m.priority, MissionLifecycle.QUEUED, m.created_at, m.resumed_count, m.meta)
            self._missions[mission_id] = m
            self._queue.append(mission_id)
            self._queue.sort(key=lambda mid: self._missions[mid].priority)
            return m
        return None

    def dequeue(self) -> ManagedMission | None:
        if not self._queue:
            return None
        mid = self._queue.pop(0)
        m = self._missions[mid]
        updated = ManagedMission(m.mission_id, m.objective, m.risk_level, m.priority, MissionLifecycle.PLANNED, m.created_at, m.resumed_count, m.meta)
        self._missions[mid] = updated
        return updated

    def advance(self, mission_id: str, target: MissionLifecycle) -> ManagedMission | None:
        m = self._missions.get(mission_id)
        if m is None:
            return None
        legal = {
            MissionLifecycle.CREATED: [MissionLifecycle.QUEUED],
            MissionLifecycle.QUEUED: [MissionLifecycle.PLANNED],
            MissionLifecycle.PLANNED: [MissionLifecycle.APPROVED],
            MissionLifecycle.APPROVED: [MissionLifecycle.EXECUTING],
            MissionLifecycle.EXECUTING: [MissionLifecycle.EVALUATING, MissionLifecycle.PAUSED],
            MissionLifecycle.EVALUATING: [MissionLifecycle.COMPLETED, MissionLifecycle.FAILED],
            MissionLifecycle.COMPLETED: [MissionLifecycle.ARCHIVED],
            MissionLifecycle.FAILED: [MissionLifecycle.QUEUED],
            MissionLifecycle.PAUSED: [MissionLifecycle.EXECUTING],
        }
        allowed = legal.get(m.status, [])
        if target not in allowed:
            return None
        updated = ManagedMission(m.mission_id, m.objective, m.risk_level, m.priority, target, m.created_at, m.resumed_count, m.meta)
        self._missions[mission_id] = updated
        return updated

    def pause(self, mission_id: str) -> ManagedMission | None:
        return self.advance(mission_id, MissionLifecycle.PAUSED)

    def resume(self, mission_id: str) -> ManagedMission | None:
        m = self._missions.get(mission_id)
        if m is None or m.status != MissionLifecycle.PAUSED:
            return None
        updated = ManagedMission(m.mission_id, m.objective, m.risk_level, m.priority, MissionLifecycle.EXECUTING, m.created_at, m.resumed_count + 1, m.meta)
        self._missions[mission_id] = updated
        return updated

    def get(self, mission_id: str) -> ManagedMission | None:
        return self._missions.get(mission_id)

    def list_by_status(self, status: MissionLifecycle) -> list[ManagedMission]:
        return [m for m in self._missions.values() if m.status == status]

    def list_active(self) -> list[ManagedMission]:
        active = {MissionLifecycle.QUEUED, MissionLifecycle.PLANNED, MissionLifecycle.EXECUTING, MissionLifecycle.EVALUATING}
        return [m for m in self._missions.values() if m.status in active]

    def queue_size(self) -> int:
        return len(self._queue)

    def stats(self) -> dict[str, Any]:
        return {"total": len(self._missions), "queued": self.queue_size(),
                "active": len(self.list_active()), "by_status": {s.value: len(self.list_by_status(s)) for s in MissionLifecycle}}
