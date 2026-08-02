"""Autonomous Scheduler — timed, conditional, and periodic mission triggers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from nexara_prime.models import now_iso, new_id


class TriggerType(str, Enum):
    TIME = "time"
    CONDITION = "condition"
    PERIODIC = "periodic"
    EVENT = "event"


@dataclass
class ScheduledMission:
    schedule_id: str
    mission_objective: str
    trigger_type: TriggerType
    trigger_spec: str  # e.g. "0 9 * * *", "every_1h", "on_test_failure"
    risk_level: str = "R2"
    enabled: bool = True
    last_triggered: str = ""
    created_at: str = field(default_factory=now_iso)


class MissionScheduler:
    """Schedules autonomous missions with time, condition, and periodic triggers."""

    def __init__(self) -> None:
        self._schedules: dict[str, ScheduledMission] = {}
        self._history: list[dict[str, Any]] = []

    def schedule(self, objective: str, trigger_type: TriggerType, trigger_spec: str, risk_level: str = "R2") -> ScheduledMission:
        sid = new_id("sch")
        sm = ScheduledMission(sid, objective, trigger_type, trigger_spec, risk_level)
        self._schedules[sid] = sm
        return sm

    def trigger(self, schedule_id: str) -> ScheduledMission | None:
        sm = self._schedules.get(schedule_id)
        if sm is None or not sm.enabled:
            return None
        sm.last_triggered = now_iso()
        self._history.append({"schedule_id": schedule_id, "objective": sm.mission_objective, "triggered_at": sm.last_triggered})
        return sm

    def enable(self, schedule_id: str) -> bool:
        sm = self._schedules.get(schedule_id)
        if sm:
            sm.enabled = True
            return True
        return False

    def disable(self, schedule_id: str) -> bool:
        sm = self._schedules.get(schedule_id)
        if sm:
            sm.enabled = False
            return True
        return False

    def list_enabled(self) -> list[ScheduledMission]:
        return [s for s in self._schedules.values() if s.enabled]

    def list_by_type(self, trigger_type: TriggerType) -> list[ScheduledMission]:
        return [s for s in self._schedules.values() if s.trigger_type == trigger_type]

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._history[-limit:]

    def stats(self) -> dict[str, Any]:
        return {"total_schedules": len(self._schedules), "enabled": len(self.list_enabled()),
                "history_count": len(self._history), "by_type": {t.value: len(self.list_by_type(t)) for t in TriggerType}}


class TriggerEngine:
    """Evaluates trigger conditions and activates scheduled missions."""

    def __init__(self, scheduler: MissionScheduler) -> None:
        self._scheduler = scheduler

    def evaluate_condition(self, condition: str, context: dict[str, Any]) -> bool:
        """Evaluate a named condition against context."""
        ctx_lower = {k.lower(): v for k, v in context.items()}
        if condition == "test_failure":
            return ctx_lower.get("test_status") == "failed"
        if condition == "git_changed":
            return ctx_lower.get("changed_files", 0) > 0
        if condition == "high_error_rate":
            return ctx_lower.get("error_count", 0) >= 3
        return False

    def check_and_trigger(self, condition: str, context: dict[str, Any]) -> list[ScheduledMission]:
        if not self.evaluate_condition(condition, context):
            return []
        triggered = []
        for sm in self._scheduler.list_by_type(TriggerType.CONDITION):
            if sm.trigger_spec == condition:
                self._scheduler.trigger(sm.schedule_id)
                triggered.append(sm)
        return triggered
