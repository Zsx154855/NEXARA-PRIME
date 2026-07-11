from __future__ import annotations

from .events import EventBus
from .evidence import EvidenceStore
from .models import Mission, MissionState


TRANSITIONS: dict[MissionState, set[MissionState]] = {
    # Original states (preserved)
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
    # Adaptive Runtime states
    MissionState.CREATED: {MissionState.TRIAGED, MissionState.CANCELLED, MissionState.FAILED},
    MissionState.TRIAGED: {MissionState.CONTRACTED, MissionState.SCHEDULED, MissionState.DEGRADED, MissionState.CANCELLED, MissionState.FAILED},
    MissionState.CONTRACTED: {MissionState.PLANNED, MissionState.CANCELLED, MissionState.FAILED},
    MissionState.PLANNED: {MissionState.SCHEDULED, MissionState.CANCELLED, MissionState.FAILED},
    MissionState.SCHEDULED: {MissionState.AWAITING_APPROVAL, MissionState.RUNNING, MissionState.DEGRADED, MissionState.CANCELLED, MissionState.FAILED},
    MissionState.AWAITING_APPROVAL: {MissionState.RUNNING, MissionState.DEGRADED, MissionState.BLOCKED, MissionState.CANCELLED, MissionState.FAILED},
    MissionState.RUNNING: {MissionState.VERIFYING, MissionState.DEGRADED, MissionState.PAUSED, MissionState.FAILED, MissionState.ROLLING_BACK},
    MissionState.VERIFYING: {MissionState.COMPLETED, MissionState.DEGRADED, MissionState.FAILED, MissionState.ROLLING_BACK},
    MissionState.DEGRADED: {MissionState.RUNNING, MissionState.VERIFYING, MissionState.COMPLETED, MissionState.FAILED, MissionState.ROLLING_BACK, MissionState.CANCELLED},
    MissionState.PAUSED: {MissionState.RUNNING, MissionState.CANCELLED, MissionState.FAILED},
    MissionState.CANCELLED: {MissionState.ROLLED_BACK},
    MissionState.ROLLING_BACK: {MissionState.ROLLED_BACK, MissionState.FAILED},
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

    def can_escalate(self, current_mode: str, target_mode: str) -> bool:
        """Check if escalation from current_mode to target_mode is valid."""
        order = {"S0": 0, "S1": 1, "S2": 2, "S3": 3}
        return order.get(target_mode, -1) > order.get(current_mode, -1)

    def can_de_escalate(self, current_mode: str, target_mode: str) -> bool:
        """Check if de-escalation from current_mode to target_mode is valid."""
        order = {"S0": 0, "S1": 1, "S2": 2, "S3": 3}
        return order.get(target_mode, -1) < order.get(current_mode, -1)
