"""Environment Intelligence — event listening, change detection, signal analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexara_prime.models import now_iso, new_id


class EventType(str, Enum):
    FILE_CHANGE = "file_change"
    GIT_CHANGE = "git_change"
    TEST_FAILURE = "test_failure"
    SYSTEM_SIGNAL = "system_signal"
    EXTERNAL_EVENT = "external_event"


@dataclass(frozen=True)
class EnvironmentEvent:
    event_id: str
    event_type: EventType
    source: str
    detail: str
    priority: int = 5
    timestamp: str = field(default_factory=now_iso)


class EventListener:
    """Listens for environment events and queues them for analysis."""

    def __init__(self) -> None:
        self._events: list[EnvironmentEvent] = []

    def on(self, event_type: EventType, source: str, detail: str, priority: int = 5) -> EnvironmentEvent:
        e = EnvironmentEvent(new_id("evt"), event_type, source, detail, priority)
        self._events.append(e)
        return e

    def recent(self, limit: int = 20) -> list[EnvironmentEvent]:
        return self._events[-limit:]

    def by_type(self, event_type: EventType) -> list[EnvironmentEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def __len__(self) -> int:
        return len(self._events)


class ChangeDetector:
    """Detects meaningful changes from raw events."""

    def detect(self, events: list[EnvironmentEvent]) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        by_type: dict[EventType, int] = {}
        for e in events:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
        for etype, count in by_type.items():
            if count >= 2:  # cluster threshold
                changes.append({"type": etype.value, "count": count, "action": self._suggest_action(etype, count)})
        return changes

    @staticmethod
    def _suggest_action(event_type: EventType, count: int) -> str:
        if event_type == EventType.TEST_FAILURE and count >= 3:
            return "create_recovery_mission"
        if event_type == EventType.FILE_CHANGE and count >= 5:
            return "create_audit_mission"
        if event_type == EventType.GIT_CHANGE:
            return "log_and_monitor"
        return "observe"


class SignalAnalyzer:
    """Analyzes environment signals to propose autonomous missions."""

    def analyze(self, events: list[EnvironmentEvent]) -> list[dict[str, Any]]:
        proposals: list[dict[str, Any]] = []
        failures = [e for e in events if e.event_type == EventType.TEST_FAILURE]
        if len(failures) >= 2:
            proposals.append({"type": "MISSION_PROPOSAL", "mission": "fix_failing_tests", "priority": 2, "evidence": [e.event_id for e in failures[:5]]})
        file_changes = [e for e in events if e.event_type == EventType.FILE_CHANGE]
        if len(file_changes) >= 5:
            proposals.append({"type": "MISSION_PROPOSAL", "mission": "audit_recent_changes", "priority": 3, "evidence": [e.event_id for e in file_changes[:5]]})
        return proposals
