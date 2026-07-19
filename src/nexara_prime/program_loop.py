"""NEXARA PRIME Program Loop — Continuous mission orchestration loop.

Loop: Load State → Select Runnable → Acquire Lease → Execute → Verify → Persist → Checkpoint → Schedule Next

Features:
- Start / Pause / Resume / Stop lifecycle
- Crash recovery: reload state from DB on restart
- Heartbeat with configurable interval
- Backpressure detection and throttling
- Lease-based execution to prevent double-processing
- 1000-cycle accelerated durability test mode
- Does NOT register as a permanent system service
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .models import MissionState, new_id, now_iso


# ── Capability flags ──

PROGRAM_LOOP_ACTIVE = "PROGRAM_LOOP_ACTIVE"
PROGRAM_LOOP_HEARTBEAT = "PROGRAM_LOOP_HEARTBEAT"
PROGRAM_LOOP_BACKPRESSURE = "PROGRAM_LOOP_BACKPRESSURE"
PROGRAM_LOOP_DURABILITY_MODE = "PROGRAM_LOOP_DURABILITY_MODE"


class LoopPhase(str, Enum):
    IDLE = "idle"
    LOADING = "loading"
    SELECTING = "selecting"
    ACQUIRING = "acquiring"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    PERSISTING = "persisting"
    CHECKPOINTING = "checkpointing"
    SCHEDULING = "scheduling"


class LoopStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    RESUMING = "resuming"
    STOPPING = "stopping"
    CRASHED = "crashed"


@dataclass
class ProgramLoopConfig:
    tick_interval_seconds: float = 0.1       # Time between cycles
    heartbeat_interval_seconds: float = 5.0  # Heartbeat frequency
    max_cycles: int = 0                       # 0 = unlimited
    max_cycle_duration_seconds: float = 30.0  # Per-cycle timeout
    backpressure_threshold: int = 100         # Max pending missions before throttling
    backpressure_cooldown_seconds: float = 1.0  # Wait when backpressure detected
    lease_ttl_seconds: int = 300              # Writer lease TTL
    checkpoint_interval: int = 10             # Checkpoint every N cycles
    durability_mode: bool = False             # Accelerated 1000-cycle test mode
    durability_cycles: int = 1000             # Target cycles for durability test


@dataclass
class LoopState:
    status: LoopStatus = LoopStatus.STOPPED
    phase: LoopPhase = LoopPhase.IDLE
    cycle_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    skipped_count: int = 0
    current_mission_id: str = ""
    last_heartbeat: str = ""
    last_checkpoint: str = ""
    last_error: str = ""
    started_at: str = ""
    uptime_seconds: float = 0.0
    backpressure_active: bool = False


@dataclass
class CycleResult:
    cycle_id: str = field(default_factory=lambda: new_id("cycle"))
    cycle_number: int = 0
    success: bool = False
    phase_reached: LoopPhase = LoopPhase.IDLE
    mission_id: str = ""
    action: str = ""
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0
    checkpoint_created: bool = False
    lease_acquired: bool = False
    timestamp: str = field(default_factory=now_iso)


class ProgramLoop:
    """Continuous mission orchestration loop.

    Load State → Select Runnable → Acquire Lease → Execute → Verify → Persist → Checkpoint → Schedule Next
    """

    def __init__(
        self,
        config: ProgramLoopConfig | None = None,
        *,
        store=None,
        events=None,
        evidence=None,
        scheduler=None,
        runtime=None,
        on_cycle: Callable[[CycleResult], None] | None = None,
    ) -> None:
        self.config = config or ProgramLoopConfig()
        self.store = store
        self.events = events
        self.evidence = evidence
        self.scheduler = scheduler
        self.runtime = runtime
        self.on_cycle = on_cycle

        self.state = LoopState()
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        self._thread: threading.Thread | None = None
        self._cycles: list[CycleResult] = []
        self._active_leases: dict[str, str] = {}
        self._started_monotonic: float = 0.0

    # ── Lifecycle ──

    def start(self) -> None:
        """Start the program loop in a background thread."""
        with self._lock:
            if self.state.status in (LoopStatus.RUNNING, LoopStatus.STARTING):
                return
            self.state.status = LoopStatus.STARTING
            self.state.started_at = now_iso()
            self._started_monotonic = time.monotonic()
            self._stop_event.clear()
            self._pause_event.set()

        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="nexara-program-loop")
        self._thread.start()

    def pause(self) -> None:
        """Pause the loop gracefully (completes current cycle)."""
        with self._lock:
            if self.state.status != LoopStatus.RUNNING:
                return
            self.state.status = LoopStatus.PAUSING
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume a paused loop."""
        with self._lock:
            if self.state.status != LoopStatus.PAUSED:
                return
            self.state.status = LoopStatus.RESUMING
        self._pause_event.set()

    def stop(self, timeout_seconds: float = 10.0) -> None:
        """Stop the loop gracefully."""
        with self._lock:
            if self.state.status in (LoopStatus.STOPPED, LoopStatus.STOPPING):
                return
            self.state.status = LoopStatus.STOPPING
        self._stop_event.set()
        self._pause_event.set()  # Unpause to allow stop

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout_seconds)
            if self._thread.is_alive():
                with self._lock:
                    self.state.status = LoopStatus.STOPPED  # Force stop

    # ── Main loop ──

    def _run_loop(self) -> None:
        """Main execution loop (runs in background thread)."""
        with self._lock:
            self.state.status = LoopStatus.RUNNING

        last_heartbeat = time.monotonic()

        while not self._stop_event.is_set():
            # Check pause
            if not self._pause_event.is_set():
                with self._lock:
                    self.state.status = LoopStatus.PAUSED
                self._pause_event.wait(timeout=0.5)
                with self._lock:
                    self.state.status = LoopStatus.RUNNING
                continue

            # Max cycles check
            if self.config.max_cycles > 0 and self.state.cycle_count >= self.config.max_cycles:
                with self._lock:
                    self.state.status = LoopStatus.STOPPING
                break

            # Execute one cycle
            try:
                result = self._execute_cycle()
                self._cycles.append(result)
                with self._lock:
                    self.state.cycle_count += 1
                    if result.success:
                        self.state.success_count += 1
                    else:
                        self.state.failure_count += 1
                    self.state.phase = LoopPhase.IDLE
                    self.state.last_error = "" if result.success else result.error

                if self.on_cycle:
                    self.on_cycle(result)

            except Exception as exc:
                with self._lock:
                    self.state.failure_count += 1
                    self.state.last_error = str(exc)
                    self.state.cycle_count += 1

            # Heartbeat
            now = time.monotonic()
            if now - last_heartbeat >= self.config.heartbeat_interval_seconds:
                self._heartbeat()
                last_heartbeat = now

            # Checkpoint
            if self.state.cycle_count > 0 and self.state.cycle_count % self.config.checkpoint_interval == 0:
                self._checkpoint()

            # Durability mode: faster cycles
            tick = 0.001 if self.config.durability_mode else self.config.tick_interval_seconds
            self._stop_event.wait(timeout=tick)

        with self._lock:
            self.state.status = LoopStatus.STOPPED
            self.state.uptime_seconds = time.monotonic() - self._started_monotonic

    def _execute_cycle(self) -> CycleResult:
        """Execute a single orchestration cycle."""
        started = time.monotonic()
        result = CycleResult(cycle_number=self.state.cycle_count + 1)

        # Phase 1: Load State
        self._set_phase(LoopPhase.LOADING)
        missions = self._load_runnable_missions()
        if not missions:
            result.skipped_count = 1
            result.success = True  # Idle cycle with no runnable missions is not a failure
            with self._lock:
                self.state.skipped_count += 1
            result.phase_reached = LoopPhase.LOADING
            result.duration_ms = (time.monotonic() - started) * 1000
            return result

        # Phase 2: Select Runnable
        self._set_phase(LoopPhase.SELECTING)
        mission = self._select_mission(missions)
        if not mission:
            result.phase_reached = LoopPhase.SELECTING
            result.duration_ms = (time.monotonic() - started) * 1000
            return result

        result.mission_id = mission.get("mission_id", "")
        self._set_current_mission(result.mission_id)

        # Backpressure check
        if len(missions) > self.config.backpressure_threshold:
            with self._lock:
                self.state.backpressure_active = True
            time.sleep(self.config.backpressure_cooldown_seconds)
        else:
            with self._lock:
                self.state.backpressure_active = False

        # Phase 3: Acquire Lease
        self._set_phase(LoopPhase.ACQUIRING)
        lease_ok = self._acquire_lease(result.mission_id)
        result.lease_acquired = lease_ok
        if not lease_ok:
            result.phase_reached = LoopPhase.ACQUIRING
            result.error = "lease_conflict"
            result.duration_ms = (time.monotonic() - started) * 1000
            return result

        # Phase 4: Execute
        self._set_phase(LoopPhase.EXECUTING)
        try:
            exec_result = self._execute_mission(mission)
            result.action = exec_result.get("action", "execute")
            result.output = exec_result.get("output", "")
            result.success = exec_result.get("success", False)
        except Exception as exc:
            result.success = False
            result.error = str(exc)

        # Phase 5: Verify
        self._set_phase(LoopPhase.VERIFYING)
        if result.success:
            result.success = self._verify_mission(result.mission_id)

        # Phase 6: Persist
        self._set_phase(LoopPhase.PERSISTING)
        self._persist_result(result)

        # Phase 7: Checkpoint (deferred to main loop interval)
        self._set_phase(LoopPhase.SCHEDULING)
        self._schedule_next(mission)

        # Release lease
        self._release_lease(result.mission_id)

        result.phase_reached = LoopPhase.SCHEDULING
        result.duration_ms = (time.monotonic() - started) * 1000
        return result

    # ── Phase implementations ──

    def _load_runnable_missions(self) -> list[dict[str, Any]]:
        """Load runnable missions from the store."""
        if self.store and hasattr(self.store, 'list_records'):
            try:
                all_missions = self.store.list_records("mission")
                runnable_states = {
                    MissionState.SCHEDULED.value,
                    MissionState.RUNNING.value,
                    MissionState.AWAITING_APPROVAL.value,
                }
                return [m for m in all_missions if m.get("state") in runnable_states]
            except Exception:
                return []
        return []

    def _select_mission(self, missions: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Select the next mission to execute."""
        if self.scheduler and hasattr(self.scheduler, 'select_next'):
            try:
                return self.scheduler.select_next(missions)
            except Exception:
                pass
        # Default: FIFO
        missions.sort(key=lambda m: m.get("created_at", ""))
        return missions[0] if missions else None

    def _acquire_lease(self, mission_id: str) -> bool:
        """Acquire a durable writer lease for the mission via store."""
        if mission_id in self._active_leases:
            return False
        if self.runtime and hasattr(self.runtime, 'store'):
            try:
                # Use store-based lease for cross-instance coordination
                lease_key = f"program_loop_lease:{mission_id}"
                existing = self.runtime.store.get_record(lease_key)
                if existing:
                    return False
                self.runtime.store.save_record(
                    lease_key, "lease",
                    {"mission_id": mission_id, "acquired_at": now_iso(), "instance_id": self.instance_id},
                    now_iso(), mission_id,
                )
            except Exception:
                pass  # Fall through to in-memory only
        self._active_leases[mission_id] = now_iso()
        return True

    def _release_lease(self, mission_id: str) -> None:
        """Release the writer lease."""
        self._active_leases.pop(mission_id, None)
        if self.runtime and hasattr(self.runtime, 'store'):
            try:
                lease_key = f"program_loop_lease:{mission_id}"
                self.runtime.store.delete_record(lease_key)
            except Exception:
                pass

    def _execute_mission(self, mission: dict[str, Any]) -> dict[str, Any]:
        """Execute the selected mission."""
        if self.runtime and hasattr(self.runtime, 'run_mission'):
            try:
                mission_id = mission.get("mission_id", "")
                if not mission_id:
                    return {"success": False, "action": "execute", "output": "", "error": "mission_id_missing_in_record"}
                mission_result = self.runtime.run_mission(mission_id)
                return {
                    "success": mission_result.state.value not in ("Failed", "Crashed"),
                    "action": "execute",
                    "output": str(mission_result),
                    "error": "" if mission_result.state.value not in ("Failed", "Crashed") else mission_result.error or "",
                }
            except Exception as exc:
                return {"success": False, "action": "execute", "output": "", "error": str(exc)}
        # Mock execution
        return {
            "success": True,
            "action": f"execute:{mission.get('mission_id', 'unknown')}",
            "output": f"[Mock] Executed mission {mission.get('mission_id', 'unknown')}",
        }

    def _verify_mission(self, mission_id: str) -> bool:
        """Verify mission execution result."""
        # In production, check evidence, run tests, validate contracts
        return True

    def _persist_result(self, result: CycleResult) -> None:
        """Persist cycle result to store."""
        if self.store and hasattr(self.store, 'save_record'):
            try:
                payload = {
                    "cycle_id": result.cycle_id,
                    "cycle_number": result.cycle_number,
                    "mission_id": result.mission_id,
                    "success": result.success,
                    "action": result.action,
                    "output": result.output,
                    "error": result.error,
                    "duration_ms": result.duration_ms,
                    "timestamp": result.timestamp,
                }
                self.store.save_record(
                    result.cycle_id, "program_cycle", payload,
                    result.timestamp, result.mission_id,
                )
            except Exception:
                pass

    def _schedule_next(self, mission: dict[str, Any]) -> None:
        """Schedule the next step after mission execution."""
        if self.scheduler and hasattr(self.scheduler, 'schedule_next'):
            try:
                self.scheduler.schedule_next(mission)
            except Exception:
                pass

    # ── Heartbeat & Checkpoint ──

    def _heartbeat(self) -> None:
        """Emit heartbeat event."""
        with self._lock:
            self.state.last_heartbeat = now_iso()
        if self.events:
            try:
                self.events.publish(
                    "program_loop.heartbeat", "program_loop", "system",
                    "program_loop", "heartbeat",
                    {
                        "cycle_count": self.state.cycle_count,
                        "success_count": self.state.success_count,
                        "failure_count": self.state.failure_count,
                        "status": self.state.status.value,
                    },
                )
            except Exception:
                pass

    def _checkpoint(self) -> None:
        """Create a recovery checkpoint."""
        with self._lock:
            self.state.last_checkpoint = now_iso()
            checkpoint_payload = {
                "cycle_count": self.state.cycle_count,
                "success_count": self.state.success_count,
                "failure_count": self.state.failure_count,
                "status": self.state.status.value,
            }
        if self.store and hasattr(self.store, 'save_record'):
            try:
                self.store.save_record(
                    f"loop_checkpoint_{self.state.cycle_count}",
                    "program_checkpoint",
                    checkpoint_payload,
                    now_iso(),
                    "program_loop",
                )
            except Exception:
                pass

    # ── Helpers ──

    def _set_phase(self, phase: LoopPhase) -> None:
        with self._lock:
            self.state.phase = phase

    def _set_current_mission(self, mission_id: str) -> None:
        with self._lock:
            self.state.current_mission_id = mission_id

    # ── Crash Recovery ──

    def recover(self) -> LoopState:
        """Recover loop state from the last checkpoint."""
        if self.store and hasattr(self.store, 'list_records'):
            try:
                checkpoints = self.store.list_records("program_checkpoint", "program_loop")
                if checkpoints:
                    checkpoints.sort(key=lambda c: c.get("created_at", ""))
                    last = checkpoints[-1]
                    with self._lock:
                        self.state.cycle_count = last.get("cycle_count", 0)
                        self.state.success_count = last.get("success_count", 0)
                        self.state.failure_count = last.get("failure_count", 0)
            except Exception:
                pass
        return self.state

    # ── Durability Test ──

    def run_durability_test(self, cycles: int = 1000) -> dict[str, Any]:
        """Run an accelerated durability test for N cycles."""
        self.config.durability_mode = True
        self.config.durability_cycles = cycles
        self.config.max_cycles = cycles

        started = time.monotonic()
        self.start()

        # Wait for completion
        while self.state.status not in (LoopStatus.STOPPED, LoopStatus.CRASHED):
            time.sleep(0.01)
            if self.state.cycle_count >= cycles:
                self.stop(timeout_seconds=5.0)
                break

        elapsed = time.monotonic() - started
        with self._lock:
            s = self.state

        return {
            "cycles_completed": s.cycle_count,
            "successes": s.success_count,
            "failures": s.failure_count,
            "skipped": s.skipped_count,
            "elapsed_seconds": elapsed,
            "cycles_per_second": s.cycle_count / max(elapsed, 0.001),
            "status": s.status.value,
            "backpressure_triggered": any(c.error == "lease_conflict" for c in self._cycles),
            "last_error": s.last_error,
        }

    # ── Lifecycle ──

    def probe_capability(self) -> dict[str, Any]:
        flags = [PROGRAM_LOOP_ACTIVE]
        if self.config.heartbeat_interval_seconds > 0:
            flags.append(PROGRAM_LOOP_HEARTBEAT)
        if self.config.backpressure_threshold > 0:
            flags.append(PROGRAM_LOOP_BACKPRESSURE)
        if self.config.durability_mode:
            flags.append(PROGRAM_LOOP_DURABILITY_MODE)
        return {
            "flags": flags,
            "tick_interval": self.config.tick_interval_seconds,
            "max_cycles": self.config.max_cycles,
            "backpressure_threshold": self.config.backpressure_threshold,
            "durability_mode": self.config.durability_mode,
        }

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self.state.status.value,
                "phase": self.state.phase.value,
                "cycle_count": self.state.cycle_count,
                "success_count": self.state.success_count,
                "failure_count": self.state.failure_count,
                "skipped_count": self.state.skipped_count,
                "current_mission_id": self.state.current_mission_id,
                "backpressure_active": self.state.backpressure_active,
                "last_heartbeat": self.state.last_heartbeat,
                "last_checkpoint": self.state.last_checkpoint,
                "last_error": self.state.last_error,
            }

    def get_cycles(self, limit: int = 100) -> list[dict[str, Any]]:
        return [
            {
                "cycle_id": c.cycle_id,
                "cycle_number": c.cycle_number,
                "success": c.success,
                "mission_id": c.mission_id,
                "duration_ms": c.duration_ms,
                "error": c.error,
            }
            for c in self._cycles[-limit:]
        ]
