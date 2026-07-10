from __future__ import annotations

from .events import EventBus
from .evidence import EvidenceStore
from .models import Mission, MissionState


TRANSITIONS: dict[MissionState, set[MissionState]] = {
    MissionState.INTENT: {MissionState.CONTEXT, MissionState.BLOCKED, MissionState.FAILED},
    MissionState.CONTEXT: {MissionState.CONTRACT, MissionState.BLOCKED, MissionState.FAILED},
    MissionState.CONTRACT: {MissionState.PLAN, MissionState.BLOCKED, MissionState.FAILED},
    MissionState.PLAN: {MissionState.SIMULATION, MissionState.BLOCKED, MissionState.FAILED},
    MissionState.SIMULATION: {MissionState.APPROVAL, MissionState.EXECUTION, MissionState.BLOCKED, MissionState.FAILED},
    MissionState.APPROVAL: {MissionState.EXECUTION, MissionState.BLOCKED, MissionState.FAILED},
    MissionState.EXECUTION: {MissionState.VERIFICATION, MissionState.BLOCKED, MissionState.FAILED, MissionState.ROLLED_BACK},
    MissionState.VERIFICATION: {MissionState.EVIDENCE, MissionState.BLOCKED, MissionState.FAILED, MissionState.ROLLED_BACK},
    MissionState.EVIDENCE: {MissionState.MEMORY_PATCH, MissionState.BLOCKED, MissionState.FAILED},
    MissionState.MEMORY_PATCH: {MissionState.EVALUATION, MissionState.BLOCKED, MissionState.FAILED},
    MissionState.EVALUATION: {MissionState.COMPLETED, MissionState.BLOCKED, MissionState.FAILED, MissionState.ROLLED_BACK},
    MissionState.COMPLETED: {MissionState.ROLLED_BACK},
    MissionState.BLOCKED: {MissionState.FAILED, MissionState.ROLLED_BACK},
    MissionState.FAILED: {MissionState.ROLLED_BACK},
    MissionState.ROLLED_BACK: set(),
}


class MissionStateMachine:
    def __init__(self, events: EventBus, evidence: EvidenceStore):
        self.events = events
        self.evidence = evidence

    def can_transition(self, current: MissionState, target: MissionState) -> bool:
        return target in TRANSITIONS.get(current, set())

    def transition(self, mission: Mission, target: MissionState, actor: str) -> tuple[Mission, object]:
        current = MissionState(mission.state)
        if not self.can_transition(current, target):
            raise ValueError(f"invalid_transition:{current.value}->{target.value}")
        event = self.events.publish(
            "mission.state_changed", mission.mission_id, "mission", actor, mission.trace_id,
            {"from": current.value, "to": target.value},
        )
        mission.state = target
        mission.updated_at = event.timestamp
        self.evidence.state_change(mission.mission_id, current.value, target.value, mission.trace_id, event.event_id)
        return mission, event
