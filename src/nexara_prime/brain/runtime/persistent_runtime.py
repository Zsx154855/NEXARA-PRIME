"""Persistent Runtime — state save/restore with recovery for autonomous operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nexara_prime.models import now_iso, new_id


@dataclass
class RuntimeState:
    checkpoint_id: str
    mission_id: str
    execution_state: str  # last known state label
    agent_state: dict[str, Any] = field(default_factory=dict)
    memory_context: list[str] = field(default_factory=list)
    evidence_pointer: str = ""
    saved_at: str = field(default_factory=now_iso)
    restored_at: str = ""
    restored_count: int = 0


class StateManager:
    """Manages runtime state save/load with checkpoint validation."""

    def __init__(self) -> None:
        self._states: dict[str, RuntimeState] = {}
        self._checkpoints: dict[str, list[str]] = {}

    def save(self, mission_id: str, execution_state: str, **kwargs: Any) -> RuntimeState:
        cid = new_id("chk")
        state = RuntimeState(checkpoint_id=cid, mission_id=mission_id, execution_state=execution_state, **kwargs)
        self._states[cid] = state
        self._checkpoints.setdefault(mission_id, []).append(cid)
        return state

    def load(self, mission_id: str) -> RuntimeState | None:
        checkpoints = self._checkpoints.get(mission_id, [])
        if not checkpoints:
            return None
        latest = checkpoints[-1]
        state = self._states[latest]
        state.restored_at = now_iso()
        state.restored_count += 1
        return state

    def list_checkpoints(self, mission_id: str) -> list[RuntimeState]:
        return [self._states[cid] for cid in self._checkpoints.get(mission_id, [])]

    def validate(self, checkpoint_id: str) -> bool:
        return checkpoint_id in self._states

    def stats(self) -> dict[str, Any]:
        return {"total_checkpoints": len(self._states), "missions_tracked": len(self._checkpoints)}


class RecoveryEngine:
    """Mission interruption recovery — validate state and resume from checkpoint."""

    def __init__(self, state_manager: StateManager) -> None:
        self._sm = state_manager
        self._recoveries: list[dict[str, Any]] = []

    def recover(self, mission_id: str) -> RuntimeState | None:
        state = self._sm.load(mission_id)
        if state is None:
            self._recoveries.append({"mission_id": mission_id, "status": "no_checkpoint", "timestamp": now_iso()})
            return None
        if not self._sm.validate(state.checkpoint_id):
            self._recoveries.append({"mission_id": mission_id, "status": "invalid_checkpoint", "timestamp": now_iso()})
            return None
        self._recoveries.append({"mission_id": mission_id, "status": "recovered", "checkpoint_id": state.checkpoint_id, "timestamp": now_iso()})
        return state

    def can_recover(self, mission_id: str) -> bool:
        return len(self._sm.list_checkpoints(mission_id)) > 0

    def recovery_log(self) -> list[dict[str, Any]]:
        return list(self._recoveries)
