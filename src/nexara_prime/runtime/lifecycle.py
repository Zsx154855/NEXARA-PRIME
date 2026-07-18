"""Runtime lifecycle state machine — OFFLINE → ONLINE → STOPPED."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum

from nexara_prime.models import now_iso


class LifecycleState(str, Enum):
    OFFLINE = "offline"
    STARTING = "starting"
    RECOVERING = "recovering"
    ONLINE = "online"
    PAUSING = "pausing"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    FAILED = "failed"


VALID_LIFECYCLE_TRANSITIONS: dict[LifecycleState, set[LifecycleState]] = {
    LifecycleState.OFFLINE: {LifecycleState.STARTING, LifecycleState.RECOVERING},
    LifecycleState.STARTING: {LifecycleState.ONLINE, LifecycleState.DEGRADED, LifecycleState.FAILED},
    LifecycleState.RECOVERING: {LifecycleState.ONLINE, LifecycleState.DEGRADED, LifecycleState.FAILED},
    LifecycleState.ONLINE: {LifecycleState.PAUSING, LifecycleState.STOPPING, LifecycleState.DEGRADED, LifecycleState.BLOCKED, LifecycleState.FAILED},
    LifecycleState.PAUSING: {LifecycleState.PAUSED, LifecycleState.FAILED},
    LifecycleState.PAUSED: {LifecycleState.ONLINE, LifecycleState.STOPPING, LifecycleState.FAILED},
    LifecycleState.STOPPING: {LifecycleState.STOPPED, LifecycleState.FAILED},
    LifecycleState.STOPPED: {LifecycleState.STARTING, LifecycleState.RECOVERING},
    LifecycleState.DEGRADED: {LifecycleState.ONLINE, LifecycleState.STOPPING, LifecycleState.BLOCKED, LifecycleState.FAILED},
    LifecycleState.BLOCKED: {LifecycleState.ONLINE, LifecycleState.STOPPING, LifecycleState.FAILED},
    LifecycleState.FAILED: {LifecycleState.RECOVERING, LifecycleState.STOPPING},
}


@dataclass
class LifecycleRecord:
    state: LifecycleState = LifecycleState.OFFLINE
    started_at: str = ""
    online_at: str = ""
    paused_at: str = ""
    stopped_at: str = ""
    last_heartbeat_at: str = ""
    last_checked_at: str = field(default_factory=now_iso)
    version: str = "1.0.0"


class RuntimeLifecycle:
    """Manages the NEXARA PRIME runtime lifecycle.

    Startup sequence:
    1. Validate Constitution
    2. Load Agent Identity
    3. Load Owner Model
    4. Validate Database & Schema
    5. Recover Runtime Truth
    6. Recover Unfinished Programs
    7. Recover Unfinished Missions
    8. Validate Transaction/Effect State
    9. Validate Evidence/Receipt Chain
    10. Recover Memory
    11. Load Worker Registry
    12. Run Doctor
    13. Start Heartbeat
    14. Enter ONLINE
    15. Execute Portfolio Loop

    Shutdown sequence:
    1. Stop accepting new programs
    2. Wait for safe checkpoint
    3. Persist Portfolio Snapshot
    4. Persist Agent State
    5. Release Leases
    6. Write Stop Evidence
    7. Enter STOPPED
    """

    def __init__(self) -> None:
        self._record = LifecycleRecord()
        self._lock = threading.RLock()
        self._startup_steps: list[tuple[str, bool, str]] = []
        self._shutdown_steps: list[tuple[str, bool, str]] = []

    @property
    def state(self) -> LifecycleState:
        return self._record.state

    @property
    def record(self) -> LifecycleRecord:
        return self._record

    def transition(
        self, target: LifecycleState, reason: str = ""
    ) -> bool:
        """Attempt a lifecycle transition. Returns True if legal."""
        with self._lock:
            allowed = VALID_LIFECYCLE_TRANSITIONS.get(self._record.state, set())
            if target not in allowed:
                return False
            self._record.state = target
            now = now_iso()
            if target == LifecycleState.ONLINE:
                self._record.online_at = now
            elif target == LifecycleState.PAUSED:
                self._record.paused_at = now
            elif target == LifecycleState.STOPPED:
                self._record.stopped_at = now
            self._record.last_checked_at = now
            return True

    def record_startup_step(self, step: str, success: bool, detail: str = "") -> None:
        self._startup_steps.append((step, success, detail))

    def record_shutdown_step(self, step: str, success: bool, detail: str = "") -> None:
        self._shutdown_steps.append((step, success, detail))

    def startup_report(self) -> dict:
        return {
            "state": self._record.state.value,
            "started_at": self._record.started_at,
            "online_at": self._record.online_at,
            "steps": [
                {"step": s, "ok": ok, "detail": d}
                for s, ok, d in self._startup_steps
            ],
        }

    def is_safe_to_stop(self) -> bool:
        """Check if it's safe to stop — no irreversible effects in progress."""
        return self._record.state in {
            LifecycleState.ONLINE,
            LifecycleState.DEGRADED,
            LifecycleState.PAUSED,
            LifecycleState.BLOCKED,
        }
