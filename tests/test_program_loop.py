"""Tests for nexara_prime.program_loop — ProgramLoop orchestration loop.

Covers:
- Dataclasses & enums (ProgramLoopConfig, LoopState, CycleResult, LoopPhase, LoopStatus)
- Lifecycle (start, stop, pause, resume, idempotency)
- Leases (acquire, release, duplicate deny, cross-instance via store)
- Heartbeat (interval gating, event emission)
- Backpressure (threshold trigger, cooldown, inactivity)
- Cycle execution (empty missions, lease conflict, execution, verify, persist)
- Max cycles enforcement, durability mode tick
- Checkpoint interval, crash recovery
- Durability test (run_durability_test)
- State helpers (get_state, get_cycles, probe_capability)
- Thread safety & edge cases
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from nexara_prime.models import MissionState, new_id, now_iso
from nexara_prime.program_loop import (
    PROGRAM_LOOP_ACTIVE,
    PROGRAM_LOOP_BACKPRESSURE,
    PROGRAM_LOOP_DURABILITY_MODE,
    PROGRAM_LOOP_HEARTBEAT,
    CycleResult,
    LoopPhase,
    LoopState,
    LoopStatus,
    ProgramLoop,
    ProgramLoopConfig,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_mock_store(missions=None):
    """Create a mock store with optional mission list."""
    store = MagicMock()
    store.list_records.return_value = missions or []
    return store


def _make_mock_events():
    """Create a mock events bus."""
    return MagicMock()


def _make_mock_scheduler(select_next=...):
    """Create a mock scheduler.

    Args:
        select_next: Return value for select_next(). Use ... (default) to leave unset
                     (MagicMock default behavior). Pass None explicitly to return None.
    """
    sched = MagicMock()
    if select_next is not ...:
        sched.select_next.return_value = select_next
    return sched


class _FakeMissionResult:
    """Minimal fake for runtime.run_mission return value, avoiding MagicMock attribute quirks."""
    def __init__(self, state=MissionState.COMPLETED, error=""):
        self.state = state
        self.error = error

    def __str__(self):
        return f"FakeMissionResult(state={self.state.value})"


def _make_mock_runtime(run_mission_result=None):
    """Create a mock runtime with store."""
    rt = MagicMock()
    rt.store = MagicMock()
    rt.store.get_record.return_value = None  # No existing lease
    if run_mission_result is not None:
        rt.run_mission.return_value = run_mission_result
    return rt


def _make_runnable_mission(mission_id="test_mission_1", state="Scheduled", created_at="2025-01-01T00:00:00Z"):
    return {"mission_id": mission_id, "state": state, "created_at": created_at}


def _make_cycle(cycle_number=1, success=True, mission_id="m1"):
    return CycleResult(cycle_number=cycle_number, success=success, mission_id=mission_id)


# ── Dataclass & Enum Tests ─────────────────────────────────────────────────────


class TestEnums:
    def test_loop_phase_values(self):
        assert LoopPhase.IDLE.value == "idle"
        assert LoopPhase.EXECUTING.value == "executing"
        assert LoopPhase.PERSISTING.value == "persisting"
        assert len(LoopPhase) == 9

    def test_loop_status_values(self):
        assert LoopStatus.STOPPED.value == "stopped"
        assert LoopStatus.RUNNING.value == "running"
        assert LoopStatus.PAUSED.value == "paused"
        assert LoopStatus.CRASHED.value == "crashed"
        assert len(LoopStatus) == 8


class TestProgramLoopConfig:
    def test_defaults(self):
        cfg = ProgramLoopConfig()
        assert cfg.tick_interval_seconds == 0.1
        assert cfg.heartbeat_interval_seconds == 5.0
        assert cfg.max_cycles == 0  # unlimited
        assert cfg.max_cycle_duration_seconds == 30.0
        assert cfg.backpressure_threshold == 100
        assert cfg.backpressure_cooldown_seconds == 1.0
        assert cfg.lease_ttl_seconds == 300
        assert cfg.checkpoint_interval == 10
        assert cfg.durability_mode is False
        assert cfg.durability_cycles == 1000

    def test_custom_values(self):
        cfg = ProgramLoopConfig(
            tick_interval_seconds=0.5,
            heartbeat_interval_seconds=2.0,
            max_cycles=100,
            backpressure_threshold=50,
            durability_mode=True,
            durability_cycles=500,
        )
        assert cfg.tick_interval_seconds == 0.5
        assert cfg.max_cycles == 100
        assert cfg.durability_mode is True
        assert cfg.durability_cycles == 500


class TestLoopState:
    def test_defaults(self):
        s = LoopState()
        assert s.status == LoopStatus.STOPPED
        assert s.phase == LoopPhase.IDLE
        assert s.cycle_count == 0
        assert s.success_count == 0
        assert s.failure_count == 0
        assert s.skipped_count == 0
        assert s.current_mission_id == ""
        assert s.backpressure_active is False


class TestCycleResult:
    def test_defaults(self):
        cr = CycleResult()
        assert cr.cycle_id.startswith("cycle_")
        assert cr.cycle_number == 0
        assert cr.success is False
        assert cr.phase_reached == LoopPhase.IDLE
        assert cr.checkpoint_created is False
        assert cr.lease_acquired is False

    def test_explicit_values(self):
        cr = CycleResult(cycle_number=5, success=True, mission_id="m42", action="test_action")
        assert cr.cycle_number == 5
        assert cr.success is True
        assert cr.mission_id == "m42"
        assert cr.action == "test_action"

    def test_timestamp_is_iso(self):
        cr = CycleResult()
        assert "T" in cr.timestamp  # ISO format


# ── Lifecycle Tests ────────────────────────────────────────────────────────────


class TestLifecycle:
    def test_start_transitions_to_running(self):
        loop = ProgramLoop(config=ProgramLoopConfig(tick_interval_seconds=0.01))
        loop.start()
        time.sleep(0.05)  # Allow thread to reach RUNNING
        assert loop.state.status == LoopStatus.RUNNING
        loop.stop(timeout_seconds=1.0)

    def test_start_sets_started_at(self):
        loop = ProgramLoop(config=ProgramLoopConfig(tick_interval_seconds=0.01))
        loop.start()
        time.sleep(0.02)
        assert loop.state.started_at != ""
        assert "T" in loop.state.started_at
        loop.stop(timeout_seconds=1.0)

    def test_start_when_running_is_noop(self):
        loop = ProgramLoop(config=ProgramLoopConfig(tick_interval_seconds=0.01))
        loop.start()
        time.sleep(0.05)
        assert loop.state.status == LoopStatus.RUNNING
        # Try starting again
        loop.start()
        assert loop.state.status == LoopStatus.RUNNING
        loop.stop(timeout_seconds=1.0)

    def test_start_when_starting_is_noop(self):
        loop = ProgramLoop(config=ProgramLoopConfig(tick_interval_seconds=0.1))
        # Manually set to STARTING to simulate edge case
        loop.state.status = LoopStatus.STARTING
        loop.start()
        assert loop.state.status == LoopStatus.STARTING

    def test_stop_transitions_to_stopped(self):
        loop = ProgramLoop(config=ProgramLoopConfig(tick_interval_seconds=0.01))
        loop.start()
        time.sleep(0.05)
        loop.stop(timeout_seconds=2.0)
        assert loop.state.status == LoopStatus.STOPPED

    def test_stop_when_stopped_is_noop(self):
        loop = ProgramLoop()
        assert loop.state.status == LoopStatus.STOPPED
        loop.stop(timeout_seconds=0.1)
        assert loop.state.status == LoopStatus.STOPPED

    def test_stop_when_stopping_is_noop(self):
        loop = ProgramLoop()
        loop.state.status = LoopStatus.STOPPING
        loop.stop(timeout_seconds=0.1)
        assert loop.state.status == LoopStatus.STOPPING

    def test_stop_sets_uptime(self):
        loop = ProgramLoop(config=ProgramLoopConfig(tick_interval_seconds=0.01))
        loop.start()
        time.sleep(0.05)
        loop.stop(timeout_seconds=2.0)
        assert loop.state.uptime_seconds > 0

    def test_pause_and_resume(self):
        loop = ProgramLoop(config=ProgramLoopConfig(tick_interval_seconds=0.01))
        loop.start()
        time.sleep(0.05)
        loop.pause()
        time.sleep(0.05)
        assert loop.state.status == LoopStatus.PAUSED
        loop.resume()
        time.sleep(0.05)
        assert loop.state.status == LoopStatus.RUNNING
        loop.stop(timeout_seconds=2.0)

    def test_pause_when_not_running_is_noop(self):
        loop = ProgramLoop()
        loop.pause()
        assert loop.state.status == LoopStatus.STOPPED

    def test_resume_when_not_paused_is_noop(self):
        loop = ProgramLoop()
        loop.resume()
        assert loop.state.status == LoopStatus.STOPPED

    def test_stop_force_after_timeout(self):
        """When thread doesn't exit in time, force STOPPED."""
        loop = ProgramLoop(config=ProgramLoopConfig(tick_interval_seconds=0.5))
        loop.start()
        time.sleep(0.1)
        # Use very short timeout so force path is hit
        # Note: the thread is waiting on _stop_event with 0.5s timeout,
        # so a 0.01s join timeout means the thread is still alive
        loop.stop(timeout_seconds=0.01)
        # Status should be STOPPED (force path)
        assert loop.state.status == LoopStatus.STOPPED

    def test_multiple_start_stop_cycles(self):
        loop = ProgramLoop(config=ProgramLoopConfig(tick_interval_seconds=0.01, max_cycles=1))
        loop.start()
        time.sleep(0.2)
        loop.stop(timeout_seconds=2.0)
        assert loop.state.status == LoopStatus.STOPPED
        # Restart
        loop.config.max_cycles = 1
        loop.start()
        time.sleep(0.2)
        loop.stop(timeout_seconds=2.0)
        assert loop.state.status == LoopStatus.STOPPED

    def test_background_thread_is_daemon(self):
        loop = ProgramLoop(config=ProgramLoopConfig(tick_interval_seconds=0.01))
        loop.start()
        time.sleep(0.03)
        assert loop._thread is not None
        assert loop._thread.daemon is True
        assert loop._thread.name == "nexara-program-loop"
        loop.stop(timeout_seconds=1.0)


# ── Max Cycles & Durability ────────────────────────────────────────────────────


class TestMaxCycles:
    def test_max_cycles_terminates_loop(self):
        loop = ProgramLoop(
            config=ProgramLoopConfig(
                tick_interval_seconds=0.01,
                max_cycles=3,
                heartbeat_interval_seconds=999.0,  # No heartbeat noise
                checkpoint_interval=999,  # No checkpoint noise
            )
        )
        loop.start()
        # Wait for max_cycles to be reached + some buffer
        deadline = time.monotonic() + 5.0
        while loop.state.status != LoopStatus.STOPPED and time.monotonic() < deadline:
            time.sleep(0.05)
        assert loop.state.status == LoopStatus.STOPPED
        assert loop.state.cycle_count >= 3

    def test_max_cycles_zero_is_unlimited(self):
        loop = ProgramLoop(config=ProgramLoopConfig(tick_interval_seconds=0.01, max_cycles=0))
        loop.start()
        time.sleep(0.1)
        assert loop.state.status == LoopStatus.RUNNING
        assert loop.state.cycle_count > 0
        loop.stop(timeout_seconds=2.0)

    def test_durability_mode_fast_tick(self):
        loop = ProgramLoop(
            config=ProgramLoopConfig(
                durability_mode=True,
                max_cycles=10,
                heartbeat_interval_seconds=999.0,
                checkpoint_interval=999,
            )
        )
        loop.start()
        deadline = time.monotonic() + 5.0
        while loop.state.status != LoopStatus.STOPPED and time.monotonic() < deadline:
            time.sleep(0.02)
        assert loop.state.status == LoopStatus.STOPPED
        assert loop.state.cycle_count >= 10


# ── Cycle Execution Tests ──────────────────────────────────────────────────────


class TestCycleExecution:
    def test_empty_missions_is_idle_cycle(self):
        loop = ProgramLoop(store=_make_mock_store(missions=[]))
        result = loop._execute_cycle()
        assert result.success is True  # Idle cycle counts as success
        assert result.phase_reached == LoopPhase.LOADING
        assert hasattr(result, "skipped_count")
        assert result.skipped_count == 1
        assert loop.state.skipped_count == 1

    def test_store_has_no_list_records(self):
        """Store without list_records returns empty missions."""
        store_no_list = MagicMock(spec=[])  # No list_records attribute
        loop = ProgramLoop(store=store_no_list)
        result = loop._execute_cycle()
        assert result.success is True
        assert result.phase_reached == LoopPhase.LOADING

    def test_store_list_records_raises(self):
        store = MagicMock()
        store.list_records.side_effect = RuntimeError("DB down")
        loop = ProgramLoop(store=store)
        result = loop._execute_cycle()
        assert result.success is True
        assert result.phase_reached == LoopPhase.LOADING

    def test_full_successful_cycle(self):
        store = _make_mock_store(missions=[_make_runnable_mission("m1", "Scheduled")])
        scheduler = _make_mock_scheduler(select_next=_make_runnable_mission("m1", "Scheduled"))
        # Mock runtime that returns success
        mission_result = _FakeMissionResult(state=MissionState.COMPLETED)
        rt = _make_mock_runtime(run_mission_result=mission_result)

        loop = ProgramLoop(store=store, scheduler=scheduler, runtime=rt)
        # Set instance_id needed by _acquire_lease when runtime.store exists
        loop.instance_id = "test-instance"

        result = loop._execute_cycle()
        assert result.success is True
        assert result.lease_acquired is True
        assert result.mission_id == "m1"
        assert result.phase_reached == LoopPhase.SCHEDULING

    def test_no_mission_selected(self):
        store = _make_mock_store(missions=[_make_runnable_mission("m1", "Scheduled")])
        scheduler = _make_mock_scheduler(select_next=None)  # Explicit None return
        loop = ProgramLoop(store=store, scheduler=scheduler)

        result = loop._execute_cycle()
        assert result.phase_reached == LoopPhase.SELECTING
        assert result.mission_id == ""

    def test_scheduler_select_next_raises_falls_back_to_fifo(self):
        store = _make_mock_store(missions=[
            _make_runnable_mission("m_later", "Scheduled", "2025-01-02T00:00:00Z"),
            _make_runnable_mission("m_earlier", "Scheduled", "2025-01-01T00:00:00Z"),
        ])
        scheduler = MagicMock()
        scheduler.select_next.side_effect = RuntimeError("Scheduler error")
        loop = ProgramLoop(store=store, scheduler=scheduler)

        # Should fall back to FIFO
        result = loop._execute_cycle()
        # FIFO picks the earliest created_at
        assert result.mission_id == "m_earlier"

    def test_lease_conflict_returns_early(self):
        store = _make_mock_store(missions=[_make_runnable_mission("m1", "Scheduled")])
        scheduler = _make_mock_scheduler(select_next=_make_runnable_mission("m1", "Scheduled"))

        loop = ProgramLoop(store=store, scheduler=scheduler)
        # Pre-populate active lease to cause conflict
        loop._active_leases["m1"] = now_iso()

        result = loop._execute_cycle()
        assert result.lease_acquired is False
        assert result.error == "lease_conflict"
        assert result.phase_reached == LoopPhase.ACQUIRING

    def test_execution_failure(self):
        """Mission fails — verify result is marked failed.

        NOTE: program_loop.py bug — _execute_cycle does NOT propagate
        exec_result['error'] to result.error. Only the except clause and
        lease-conflict paths set result.error.
        """
        store = _make_mock_store(missions=[_make_runnable_mission("m1", "Scheduled")])
        scheduler = _make_mock_scheduler(select_next=_make_runnable_mission("m1", "Scheduled"))
        mission_result = _FakeMissionResult(state=MissionState.FAILED, error="execution crashed")
        rt = _make_mock_runtime(run_mission_result=mission_result)

        loop = ProgramLoop(store=store, scheduler=scheduler, runtime=rt)
        loop.instance_id = "test-instance"

        result = loop._execute_cycle()
        assert result.success is False
        # BUG: error from _execute_mission is not propagated to result.error
        # expect empty until the bug is fixed; output should still reflect failure
        assert result.output.startswith("FakeMissionResult")

    def test_execution_raises_exception(self):
        """_execute_mission catches exceptions and returns error dict.

        NOTE: Same bug — _execute_cycle does not propagate the error field.
        """
        store = _make_mock_store(missions=[_make_runnable_mission("m1", "Scheduled")])
        scheduler = _make_mock_scheduler(select_next=_make_runnable_mission("m1", "Scheduled"))
        rt = _make_mock_runtime()
        rt.run_mission.side_effect = ValueError("Boom!")

        loop = ProgramLoop(store=store, scheduler=scheduler, runtime=rt)
        loop.instance_id = "test-instance"

        result = loop._execute_cycle()
        # Execution failed (exception caught by _execute_mission)
        assert result.success is False
        # BUG: _execute_cycle doesn't propagate exec_result['error']
        # The error was "Boom!" from ValueError but it's not copied to result.error

    def test_execute_mock_when_no_runtime(self):
        """When no runtime is provided, _execute_mission returns mock success."""
        store = _make_mock_store(missions=[_make_runnable_mission("m1", "Scheduled")])
        scheduler = _make_mock_scheduler(select_next=_make_runnable_mission("m1", "Scheduled"))

        loop = ProgramLoop(store=store, scheduler=scheduler)
        result = loop._execute_cycle()
        assert result.success is True
        assert "Mock" in result.output

    def test_execute_with_missing_mission_id(self):
        """Mission record with no mission_id — _execute_mission returns error dict.

        NOTE: Same bug — _execute_cycle does not propagate error field.
        """
        store = _make_mock_store(missions=[{"state": "Scheduled"}])  # No mission_id key
        scheduler = _make_mock_scheduler(select_next={"state": "Scheduled"})
        mission_result = _FakeMissionResult(state=MissionState.COMPLETED)
        rt = _make_mock_runtime(run_mission_result=mission_result)

        loop = ProgramLoop(store=store, scheduler=scheduler, runtime=rt)
        loop.instance_id = "test-instance"

        result = loop._execute_cycle()
        # _execute_mission detects missing mission_id and returns success=False
        assert result.success is False
        # BUG: error "mission_id_missing_in_record" is not propagated to result.error

    def test_runnable_states_filtering(self):
        """Only Scheduled, Running, AwaitingApproval missions are loaded."""
        store = _make_mock_store(missions=[
            {"mission_id": "m1", "state": "Scheduled"},
            {"mission_id": "m2", "state": "Running"},
            {"mission_id": "m3", "state": "AwaitingApproval"},
            {"mission_id": "m4", "state": "Completed"},
            {"mission_id": "m5", "state": "Failed"},
        ])
        loop = ProgramLoop(store=store)
        missions = loop._load_runnable_missions()
        ids = {m["mission_id"] for m in missions}
        assert ids == {"m1", "m2", "m3"}

    def test_select_mission_fifo_sort(self):
        missions = [
            {"mission_id": "m3", "created_at": "2025-03-01T00:00:00Z"},
            {"mission_id": "m1", "created_at": "2025-01-01T00:00:00Z"},
            {"mission_id": "m2", "created_at": "2025-02-01T00:00:00Z"},
        ]
        loop = ProgramLoop()
        selected = loop._select_mission(missions)
        assert selected["mission_id"] == "m1"  # Earliest

    def test_select_mission_empty_list(self):
        loop = ProgramLoop()
        assert loop._select_mission([]) is None

    def test_on_cycle_callback(self):
        store = _make_mock_store(missions=[_make_runnable_mission("m1", "Scheduled")])
        scheduler = _make_mock_scheduler(select_next=_make_runnable_mission("m1", "Scheduled"))
        callback_results = []

        loop = ProgramLoop(
            store=store,
            scheduler=scheduler,
            on_cycle=lambda r: callback_results.append(r),
            config=ProgramLoopConfig(tick_interval_seconds=0.01, max_cycles=2, checkpoint_interval=999, heartbeat_interval_seconds=999),
        )
        loop.start()
        deadline = time.monotonic() + 5.0
        while loop.state.status != LoopStatus.STOPPED and time.monotonic() < deadline:
            time.sleep(0.05)
        loop.stop(timeout_seconds=2.0)

        assert len(callback_results) >= 2
        assert all(isinstance(r, CycleResult) for r in callback_results)

    def test_cycle_exception_is_caught(self):
        """Verify that cycle-level exceptions are caught and don't crash the loop."""
        loop = ProgramLoop(config=ProgramLoopConfig(tick_interval_seconds=0.01, max_cycles=2, checkpoint_interval=999, heartbeat_interval_seconds=999))
        # Make _execute_cycle raise an exception
        loop._execute_cycle = MagicMock(side_effect=RuntimeError("Unexpected"))

        loop.start()
        deadline = time.monotonic() + 5.0
        while loop.state.status != LoopStatus.STOPPED and time.monotonic() < deadline:
            time.sleep(0.05)
        loop.stop(timeout_seconds=2.0)

        assert loop.state.failure_count > 0
        assert loop.state.last_error != ""


# ── Lease Tests ────────────────────────────────────────────────────────────────


class TestLease:
    def test_acquire_lease_in_memory(self):
        loop = ProgramLoop()
        assert loop._acquire_lease("m1") is True
        assert "m1" in loop._active_leases

    def test_acquire_duplicate_lease_denied(self):
        loop = ProgramLoop()
        loop._acquire_lease("m1")
        assert loop._acquire_lease("m1") is False

    def test_release_lease(self):
        loop = ProgramLoop()
        loop._acquire_lease("m1")
        loop._release_lease("m1")
        assert "m1" not in loop._active_leases

    def test_release_nonexistent_lease_no_error(self):
        loop = ProgramLoop()
        loop._release_lease("nonexistent")  # Should not raise

    def test_acquire_lease_with_runtime_store(self):
        rt = _make_mock_runtime()
        rt.store.get_record.return_value = None  # No existing lease
        loop = ProgramLoop(runtime=rt)
        loop.instance_id = "inst-1"

        assert loop._acquire_lease("m1") is True
        assert "m1" in loop._active_leases
        rt.store.save_record.assert_called_once()

    def test_acquire_lease_existing_in_store_denied(self):
        rt = _make_mock_runtime()
        rt.store.get_record.return_value = {"mission_id": "m1"}  # Existing lease
        loop = ProgramLoop(runtime=rt)
        loop.instance_id = "inst-1"

        assert loop._acquire_lease("m1") is False

    def test_acquire_lease_store_raises_falls_back_to_memory(self):
        rt = _make_mock_runtime()
        rt.store.get_record.side_effect = RuntimeError("DB error")
        loop = ProgramLoop(runtime=rt)
        loop.instance_id = "inst-1"

        assert loop._acquire_lease("m1") is True  # Falls through to in-memory
        assert "m1" in loop._active_leases

    def test_release_lease_with_runtime_store(self):
        rt = _make_mock_runtime()
        loop = ProgramLoop(runtime=rt)
        loop.instance_id = "inst-1"
        loop._active_leases["m1"] = now_iso()

        loop._release_lease("m1")
        assert "m1" not in loop._active_leases
        rt.store.delete_record.assert_called_once()

    def test_release_lease_store_raises_is_handled(self):
        rt = _make_mock_runtime()
        rt.store.delete_record.side_effect = RuntimeError("DB error")
        loop = ProgramLoop(runtime=rt)
        loop._active_leases["m1"] = now_iso()

        loop._release_lease("m1")  # Should not raise
        assert "m1" not in loop._active_leases  # In-memory still cleaned


# ── Backpressure Tests ─────────────────────────────────────────────────────────


class TestBackpressure:
    def test_backpressure_triggered_when_above_threshold(self):
        store = _make_mock_store(missions=[
            {"mission_id": f"m{i}", "state": "Scheduled"} for i in range(150)
        ])
        loop = ProgramLoop(store=store, config=ProgramLoopConfig(backpressure_threshold=100, backpressure_cooldown_seconds=0.01))
        loop.instance_id = "test"

        # Execute a cycle; backpressure should fire (150 > 100)
        loop._execute_cycle()
        assert loop.state.backpressure_active is True

    def test_backpressure_not_triggered_when_below_threshold(self):
        store = _make_mock_store(missions=[
            {"mission_id": f"m{i}", "state": "Scheduled"} for i in range(5)
        ])
        loop = ProgramLoop(store=store, config=ProgramLoopConfig(backpressure_threshold=100))

        loop._execute_cycle()
        assert loop.state.backpressure_active is False

    def test_backpressure_resets_when_back_to_normal(self):
        store = _make_mock_store(missions=[
            {"mission_id": f"m{i}", "state": "Scheduled"} for i in range(150)
        ])
        loop = ProgramLoop(store=store, config=ProgramLoopConfig(backpressure_threshold=100, backpressure_cooldown_seconds=0.01))
        loop.instance_id = "test"

        loop._execute_cycle()
        assert loop.state.backpressure_active is True

        # Now drop below threshold
        store.list_records.return_value = [
            {"mission_id": f"m{i}", "state": "Scheduled"} for i in range(5)
        ]
        loop._execute_cycle()
        assert loop.state.backpressure_active is False


# ── Heartbeat Tests ────────────────────────────────────────────────────────────


class TestHeartbeat:
    def test_heartbeat_updates_last_heartbeat(self):
        loop = ProgramLoop(events=_make_mock_events())
        loop._heartbeat()
        assert loop.state.last_heartbeat != ""
        assert "T" in loop.state.last_heartbeat

    def test_heartbeat_publishes_event(self):
        events = _make_mock_events()
        loop = ProgramLoop(events=events)
        loop.state.cycle_count = 5
        loop.state.success_count = 3
        loop.state.failure_count = 2

        loop._heartbeat()
        events.publish.assert_called_once()
        call_args = events.publish.call_args
        assert call_args[0][0] == "program_loop.heartbeat"
        assert call_args[0][3] == "program_loop"
        assert call_args[0][4] == "heartbeat"
        payload = call_args[0][5]
        assert payload["cycle_count"] == 5
        assert payload["success_count"] == 3
        assert payload["failure_count"] == 2

    def test_heartbeat_without_events_does_not_raise(self):
        loop = ProgramLoop()
        loop._heartbeat()  # Should not raise
        assert loop.state.last_heartbeat != ""

    def test_heartbeat_events_raises_is_handled(self):
        events = _make_mock_events()
        events.publish.side_effect = RuntimeError("Event bus down")
        loop = ProgramLoop(events=events)
        loop._heartbeat()  # Should not raise
        assert loop.state.last_heartbeat != ""

    def test_heartbeat_interval_gating(self):
        """Heartbeats fire at the configured interval."""
        loop = ProgramLoop(
            config=ProgramLoopConfig(
                tick_interval_seconds=0.01,
                heartbeat_interval_seconds=0.05,
                max_cycles=10,
                checkpoint_interval=999,
            ),
            events=_make_mock_events(),
        )
        loop.start()
        deadline = time.monotonic() + 5.0
        while loop.state.status != LoopStatus.STOPPED and time.monotonic() < deadline:
            time.sleep(0.05)
        loop.stop(timeout_seconds=2.0)

        # At least one heartbeat should have fired
        assert loop.state.last_heartbeat != ""


# ── Checkpoint Tests ───────────────────────────────────────────────────────────


class TestCheckpoint:
    def test_checkpoint_updates_last_checkpoint(self):
        loop = ProgramLoop(store=_make_mock_store())
        loop._checkpoint()
        assert loop.state.last_checkpoint != ""
        assert "T" in loop.state.last_checkpoint

    def test_checkpoint_saves_to_store(self):
        store = _make_mock_store()
        loop = ProgramLoop(store=store)
        loop.state.cycle_count = 10

        loop._checkpoint()
        store.save_record.assert_called_once()
        call_args = store.save_record.call_args
        assert call_args[0][0] == "loop_checkpoint_10"
        assert call_args[0][1] == "program_checkpoint"

    def test_checkpoint_without_store_does_not_raise(self):
        loop = ProgramLoop()
        loop._checkpoint()  # Should not raise
        assert loop.state.last_checkpoint != ""

    def test_checkpoint_store_raises_is_handled(self):
        store = _make_mock_store()
        store.save_record.side_effect = RuntimeError("Storage error")
        loop = ProgramLoop(store=store)
        loop._checkpoint()  # Should not raise
        assert loop.state.last_checkpoint != ""

    def test_checkpoint_interval_in_loop(self):
        """Checkpoint fires every checkpoint_interval cycles."""
        store = _make_mock_store()
        loop = ProgramLoop(
            store=store,
            config=ProgramLoopConfig(
                tick_interval_seconds=0.01,
                max_cycles=3,
                checkpoint_interval=2,
                heartbeat_interval_seconds=999,
            ),
        )
        loop.start()
        deadline = time.monotonic() + 5.0
        while loop.state.status != LoopStatus.STOPPED and time.monotonic() < deadline:
            time.sleep(0.05)
        loop.stop(timeout_seconds=2.0)

        # Checkpoint should have been saved (at cycle 2)
        assert loop.state.last_checkpoint != ""


# ── Crash Recovery Tests ───────────────────────────────────────────────────────


class TestRecovery:
    def test_recover_from_checkpoints(self):
        store = _make_mock_store(missions=[
            {"cycle_count": 50, "success_count": 40, "failure_count": 10, "created_at": "2025-01-01T00:00:00Z"},
            {"cycle_count": 100, "success_count": 85, "failure_count": 15, "created_at": "2025-01-02T00:00:00Z"},
        ])
        loop = ProgramLoop(store=store)
        state = loop.recover()
        assert state.cycle_count == 100
        assert state.success_count == 85
        assert state.failure_count == 15

    def test_recover_no_checkpoints(self):
        store = _make_mock_store(missions=[])
        loop = ProgramLoop(store=store)
        state = loop.recover()
        assert state.cycle_count == 0
        assert state.success_count == 0

    def test_recover_no_store(self):
        loop = ProgramLoop()
        state = loop.recover()
        assert state.cycle_count == 0

    def test_recover_store_raises_is_handled(self):
        store = MagicMock()
        store.list_records.side_effect = RuntimeError("DB error")
        loop = ProgramLoop(store=store)
        state = loop.recover()
        assert state.cycle_count == 0  # Unchanged


# ── Durability Test ────────────────────────────────────────────────────────────


class TestDurabilityTest:
    def test_run_durability_test_completes(self):
        loop = ProgramLoop(
            store=_make_mock_store(),
            config=ProgramLoopConfig(
                heartbeat_interval_seconds=999,
                checkpoint_interval=999,
            ),
        )
        result = loop.run_durability_test(cycles=3)
        assert result["cycles_completed"] >= 3
        assert result["status"] == "stopped"
        assert result["cycles_per_second"] > 0
        assert "successes" in result
        assert "failures" in result
        assert "backpressure_triggered" in result

    def test_run_durability_test_default_cycles(self):
        """Default is 1000 cycles; test with a small number to verify it works."""
        loop = ProgramLoop(
            store=_make_mock_store(),
            config=ProgramLoopConfig(
                heartbeat_interval_seconds=999,
                checkpoint_interval=999,
            ),
        )
        result = loop.run_durability_test(cycles=5)
        assert result["cycles_completed"] >= 5

    def test_run_durability_test_enables_durability_mode(self):
        loop = ProgramLoop(
            store=_make_mock_store(),
            config=ProgramLoopConfig(heartbeat_interval_seconds=999, checkpoint_interval=999),
        )
        loop.run_durability_test(cycles=2)
        assert loop.config.durability_mode is True
        assert loop.config.durability_cycles == 2


# ── State Helpers Tests ────────────────────────────────────────────────────────


class TestStateHelpers:
    def test_get_state_returns_all_fields(self):
        loop = ProgramLoop()
        loop.state.cycle_count = 5
        loop.state.success_count = 3

        state = loop.get_state()
        assert state["status"] == "stopped"
        assert state["cycle_count"] == 5
        assert state["success_count"] == 3
        assert "phase" in state
        assert "backpressure_active" in state
        assert "last_error" in state

    def test_get_cycles_returns_history(self):
        loop = ProgramLoop()
        loop._cycles = [
            _make_cycle(1, True, "m1"),
            _make_cycle(2, False, "m2"),
            _make_cycle(3, True, "m3"),
        ]
        cycles = loop.get_cycles()
        assert len(cycles) == 3
        assert cycles[0]["cycle_number"] == 1
        assert cycles[1]["cycle_number"] == 2

    def test_get_cycles_respects_limit(self):
        loop = ProgramLoop()
        loop._cycles = [_make_cycle(i + 1, True, f"m{i + 1}") for i in range(50)]
        cycles = loop.get_cycles(limit=10)
        assert len(cycles) == 10
        assert cycles[-1]["cycle_number"] == 50  # Most recent (last 10 of 50)

    def test_get_cycles_empty(self):
        loop = ProgramLoop()
        assert loop.get_cycles() == []

    def test_probe_capability_default(self):
        loop = ProgramLoop()
        caps = loop.probe_capability()
        assert PROGRAM_LOOP_ACTIVE in caps["flags"]
        assert PROGRAM_LOOP_HEARTBEAT in caps["flags"]
        assert PROGRAM_LOOP_BACKPRESSURE in caps["flags"]
        assert PROGRAM_LOOP_DURABILITY_MODE not in caps["flags"]
        assert caps["durability_mode"] is False

    def test_probe_capability_durability_mode(self):
        loop = ProgramLoop(config=ProgramLoopConfig(durability_mode=True))
        caps = loop.probe_capability()
        assert PROGRAM_LOOP_DURABILITY_MODE in caps["flags"]
        assert caps["durability_mode"] is True

    def test_probe_capability_no_heartbeat_when_zero(self):
        loop = ProgramLoop(config=ProgramLoopConfig(heartbeat_interval_seconds=0))
        caps = loop.probe_capability()
        assert PROGRAM_LOOP_HEARTBEAT not in caps["flags"]

    def test_probe_capability_no_backpressure_when_zero(self):
        loop = ProgramLoop(config=ProgramLoopConfig(backpressure_threshold=0))
        caps = loop.probe_capability()
        assert PROGRAM_LOOP_BACKPRESSURE not in caps["flags"]


# ── Phase Helpers ──────────────────────────────────────────────────────────────


class TestPhaseHelpers:
    def test_set_phase(self):
        loop = ProgramLoop()
        loop._set_phase(LoopPhase.EXECUTING)
        assert loop.state.phase == LoopPhase.EXECUTING

    def test_set_current_mission(self):
        loop = ProgramLoop()
        loop._set_current_mission("m42")
        assert loop.state.current_mission_id == "m42"


# ── Persist & Schedule Tests ───────────────────────────────────────────────────


class TestPersist:
    def test_persist_result_saves_to_store(self):
        store = _make_mock_store()
        loop = ProgramLoop(store=store)
        cr = _make_cycle(1, True, "m1")
        loop._persist_result(cr)
        store.save_record.assert_called_once()

    def test_persist_result_store_raises_is_handled(self):
        store = _make_mock_store()
        store.save_record.side_effect = RuntimeError("Store error")
        loop = ProgramLoop(store=store)
        cr = _make_cycle(1, True, "m1")
        loop._persist_result(cr)  # Should not raise

    def test_persist_result_no_store(self):
        loop = ProgramLoop()
        cr = _make_cycle(1, True, "m1")
        loop._persist_result(cr)  # Should not raise


class TestSchedule:
    def test_schedule_next_calls_scheduler(self):
        scheduler = _make_mock_scheduler()
        loop = ProgramLoop(scheduler=scheduler)
        mission = _make_runnable_mission("m1")
        loop._schedule_next(mission)
        scheduler.schedule_next.assert_called_once_with(mission)

    def test_schedule_next_no_scheduler(self):
        loop = ProgramLoop()
        loop._schedule_next({})  # Should not raise

    def test_schedule_next_scheduler_raises_is_handled(self):
        scheduler = _make_mock_scheduler()
        scheduler.schedule_next.side_effect = RuntimeError("Error")
        loop = ProgramLoop(scheduler=scheduler)
        loop._schedule_next({"mission_id": "m1"})  # Should not raise


# ── Thread Safety / Edge Cases ─────────────────────────────────────────────────


class TestThreadSafety:
    def test_state_lock_is_rlock(self):
        loop = ProgramLoop()
        assert isinstance(loop._lock, type(threading.RLock()))

    def test_stop_event_respected(self):
        loop = ProgramLoop(config=ProgramLoopConfig(tick_interval_seconds=0.01))
        loop.start()
        time.sleep(0.03)
        loop.stop(timeout_seconds=2.0)
        assert loop._stop_event.is_set()

    def test_pause_event_initial_state(self):
        loop = ProgramLoop()
        assert loop._pause_event.is_set()  # Not paused by default

    def test_config_default_after_init(self):
        loop = ProgramLoop()
        assert loop.config.tick_interval_seconds == 0.1
        assert isinstance(loop.state, LoopState)

    def test_all_dependencies_optional(self):
        """ProgramLoop should work with no dependencies at all."""
        loop = ProgramLoop()
        assert loop.store is None
        assert loop.events is None
        assert loop.scheduler is None
        assert loop.runtime is None
        # Basic operations should not crash
        loop._heartbeat()
        loop._checkpoint()
        loop._execute_cycle()
        loop.recover()
        loop.get_state()
        loop.get_cycles()
        loop.probe_capability()

    def test_pattern_flag_constants(self):
        assert PROGRAM_LOOP_ACTIVE == "PROGRAM_LOOP_ACTIVE"
        assert PROGRAM_LOOP_HEARTBEAT == "PROGRAM_LOOP_HEARTBEAT"
        assert PROGRAM_LOOP_BACKPRESSURE == "PROGRAM_LOOP_BACKPRESSURE"
        assert PROGRAM_LOOP_DURABILITY_MODE == "PROGRAM_LOOP_DURABILITY_MODE"


# ── Integration: Full Loop With Mocks ──────────────────────────────────────────


class TestIntegrationFullLoop:
    def test_full_loop_with_mock_runtime(self):
        """End-to-end test: loop runs multiple cycles with mocked runtime."""
        store = _make_mock_store(missions=[_make_runnable_mission("m1", "Scheduled")])
        scheduler = _make_mock_scheduler(select_next=_make_runnable_mission("m1", "Scheduled"))
        mission_result = MagicMock()
        mission_result.state = MissionState.COMPLETED
        mission_result.error = ""
        rt = _make_mock_runtime(run_mission_result=mission_result)
        events = _make_mock_events()

        loop = ProgramLoop(
            store=store,
            scheduler=scheduler,
            runtime=rt,
            events=events,
            config=ProgramLoopConfig(
                tick_interval_seconds=0.01,
                max_cycles=5,
                heartbeat_interval_seconds=0.05,
                checkpoint_interval=2,
            ),
        )
        loop.instance_id = "test-instance"

        loop.start()
        deadline = time.monotonic() + 10.0
        while loop.state.status != LoopStatus.STOPPED and time.monotonic() < deadline:
            time.sleep(0.05)
        loop.stop(timeout_seconds=2.0)

        assert loop.state.status == LoopStatus.STOPPED
        assert loop.state.cycle_count >= 5
        assert loop.state.success_count > 0
        # Heartbeat should have fired (0.05s interval, 5 cycles should take long enough)
        assert loop.state.last_heartbeat != ""
        # Checkpoint should have fired at cycles 2 and 4
        assert loop.state.last_checkpoint != ""

    def test_loop_persists_cycle_results(self):
        store = _make_mock_store(missions=[_make_runnable_mission("m1", "Scheduled")])
        scheduler = _make_mock_scheduler(select_next=_make_runnable_mission("m1", "Scheduled"))

        loop = ProgramLoop(
            store=store,
            scheduler=scheduler,
            config=ProgramLoopConfig(
                tick_interval_seconds=0.01,
                max_cycles=2,
                heartbeat_interval_seconds=999,
                checkpoint_interval=999,
            ),
        )
        loop.start()
        deadline = time.monotonic() + 10.0
        while loop.state.status != LoopStatus.STOPPED and time.monotonic() < deadline:
            time.sleep(0.05)
        loop.stop(timeout_seconds=2.0)

        # Cycle results should be persisted to store
        assert store.save_record.called
        # get_cycles should return results
        cycles = loop.get_cycles()
        assert len(cycles) >= 2
