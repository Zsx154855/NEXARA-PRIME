from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .db import SQLiteStore
from .events import EventBus
from .models import MissionState, new_id, now_iso


@dataclass(frozen=True)
class RecoveryResult:
    checked: int
    resumable: int
    completed: int
    duplicate_steps: int
    missions: list[dict[str, Any]]


class DurableRecovery:
    """Event-log-backed recovery metadata and idempotent execution checkpoints."""

    INCOMPLETE = {MissionState.EXECUTION.value, MissionState.VERIFICATION.value, MissionState.EVIDENCE.value, MissionState.MEMORY_PATCH.value, MissionState.EVALUATION.value}

    def __init__(self, store: SQLiteStore, events: EventBus):
        self.store = store
        self.events = events

    def checkpoint(self, mission_id: str, step: str, trace_id: str, *, status: str = "completed", data: dict[str, Any] | None = None, idempotency_key: str | None = None) -> dict[str, Any]:
        key = idempotency_key or f"checkpoint:{mission_id}:{step}"
        existing = self.store.find_record("checkpoint", "idempotency_key", key)
        if existing:
            return existing
        record = {"checkpoint_id": new_id("checkpoint"), "mission_id": mission_id, "step": step, "status": status, "data": data or {}, "trace_id": trace_id, "idempotency_key": key, "created_at": now_iso()}
        self.store.save_record(record["checkpoint_id"], "checkpoint", record, record["created_at"], mission_id)
        self.events.publish("mission.checkpoint.created", mission_id, "mission", "recovery", trace_id, record, idempotency_key=f"event:{key}")
        return record

    def checkpoint_done(self, mission_id: str, step: str) -> bool:
        return self.store.find_record("checkpoint", "idempotency_key", f"checkpoint:{mission_id}:{step}") is not None

    def recover(self) -> RecoveryResult:
        missions = self.store.list_records("mission")
        report: list[dict[str, Any]] = []
        resumable = 0
        completed = 0
        duplicate_steps = 0
        for mission in missions:
            state = mission.get("state")
            events = self.store.list_events(mission.get("mission_id"))
            transitions = [item for item in events if item.get("event_type") == "mission.state_changed"]
            if state in self.INCOMPLETE:
                resumable += 1
            if state == MissionState.COMPLETED.value:
                completed += 1
            steps = [item.get("step") for item in self.store.list_records("checkpoint", mission.get("mission_id"))]
            duplicate_steps += len(steps) - len(set(steps))
            report.append({"mission_id": mission.get("mission_id"), "state": state, "event_count": len(events), "transition_count": len(transitions), "resumable": state in self.INCOMPLETE, "checkpoint_count": len(steps), "duplicate_steps": len(steps) - len(set(steps))})
            if state in self.INCOMPLETE:
                self.events.publish("mission.recovery.checked", mission["mission_id"], "mission", "recovery", mission.get("trace_id", "recovery"), report[-1], idempotency_key=f"recovery:{mission['mission_id']}:{state}")
        return RecoveryResult(len(missions), resumable, completed, duplicate_steps, report)
