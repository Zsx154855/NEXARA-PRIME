"""NCA-01 real main regression gate.

Target: Zsx154855/NEXARA-PRIME main
Commit: f4a5400d73391280fa9c19e128edcea03cf608f1

All product classes below are imported from the actual checkout, NOT extracted
method copies. Store instances are actual SQLiteStore/StateManager. The small
SimpleNamespace is a runtime dependency carrier, not a fake persistence layer.

This is a proposed fail-closed contract suite; main is expected to be RED.
Do not use this as a release gate until its failures are independently reviewed.
"""
from __future__ import annotations

import sqlite3
import threading
from types import SimpleNamespace

import pytest

from nexara_prime.db import SQLiteStore
from nexara_prime.models import MissionState
from nexara_prime.program_loop import ProgramLoop
from nexara_prime.brain.runtime.persistent_runtime import StateManager


@pytest.fixture
def store(tmp_path):
    obj = SQLiteStore(tmp_path / "main.sqlite")
    yield obj
    obj.close()


def _loop(store, identity=None):
    loop = ProgramLoop(runtime=SimpleNamespace(store=store))
    if identity is not None:
        loop.instance_id = identity
    return loop


def test_missing_instance_identity_must_not_acquire_volatile_fallback(store):
    loop = _loop(store)  # exact NexaraRuntime lazy constructor has no instance_id
    acquired = loop._acquire_lease("mission-identity")
    assert not acquired, "Missing writer identity must fail closed, not claim a volatile lease"
    assert store.get_record("program_loop_lease:mission-identity") is None


def test_persisted_lease_owner_can_release_and_reacquire(store):
    first = _loop(store, "owner-a")
    assert first._acquire_lease("mission-restart") is True
    assert store.get_record("program_loop_lease:mission-restart") is not None
    first._release_lease("mission-restart")
    assert store.get_record("program_loop_lease:mission-restart") is None, (
        "SQLiteStore lacks delete_record; a saved lease is not actually released"
    )
    second = _loop(store, "owner-b")
    assert second._acquire_lease("mission-restart") is True


def test_concurrent_writers_need_atomic_single_winner(tmp_path):
    db = tmp_path / "concurrent.sqlite"
    left_store, right_store = SQLiteStore(db), SQLiteStore(db)
    barrier = threading.Barrier(2)
    original_left, original_right = left_store.get_record, right_store.get_record

    # Instrument only the read boundary to deterministically expose real DB
    # read-then-overwrite behavior. Both writes still invoke actual SQLiteStore.
    def left_read(key):
        result = original_left(key)
        barrier.wait(timeout=8)
        return result

    def right_read(key):
        result = original_right(key)
        barrier.wait(timeout=8)
        return result

    left_store.get_record, right_store.get_record = left_read, right_read
    left, right = _loop(left_store, "owner-left"), _loop(right_store, "owner-right")
    results = {}
    errors = []

    def claim(label, loop):
        try:
            results[label] = loop._acquire_lease("mission-concurrent")
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc}")

    try:
        threads = [threading.Thread(target=claim, args=("L", left)),
                   threading.Thread(target=claim, args=("R", right))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=12)
        assert not any(t.is_alive() for t in threads), "claim threads hung"
        assert not errors, f"lease claim exceptions: {errors}"
        assert len(results) == 2, results
        assert sum(bool(x) for x in results.values()) == 1, (
            f"Only one writer should win an atomic claim, observed {results}"
        )
    finally:
        left_store.close()
        right_store.close()


def test_unavailable_executor_must_not_forge_success():
    result = ProgramLoop()._execute_mission({"mission_id": "mission-no-executor"})
    assert result["success"] is False
    assert "Mock" not in str(result)


def test_nonterminal_runtime_state_must_not_count_as_success(store):
    runtime = SimpleNamespace(store=store, run_mission=lambda _mid: SimpleNamespace(
        state=MissionState.RUNNING, error="", mission_id="mission-running"))
    result = ProgramLoop(runtime=runtime)._execute_mission({"mission_id": "mission-running"})
    assert result["success"] is False, "Running != Completed"


def test_missing_verification_evidence_must_not_pass():
    assert ProgramLoop()._verify_mission("mission-without-evidence") is False


def test_sqlite_read_failure_must_not_be_reported_as_idle_success(tmp_path):
    disconnected = SQLiteStore(tmp_path / "closed.sqlite")
    disconnected.close()
    result = ProgramLoop(store=disconnected)._execute_cycle()
    assert result.success is False, "Closed DB must be an explicit failure, not an idle cycle"


def test_effect_consumption_must_be_scoped_by_action(tmp_path):
    path = tmp_path / "state_manager.sqlite"
    manager = StateManager(str(path))
    try:
        assert manager.record_effect("proj", "mission", "write-report", "shared-key", "hash-a")
        assert manager.record_effect("proj", "mission", "send-message", "shared-key", "hash-b")
        assert manager.consume_effect("proj", "mission", "shared-key")
    finally:
        manager.close()
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            "SELECT action, consumed_at FROM idempotency WHERE project_id=? AND mission_id=? AND idempotency_key=?",
            ("proj", "mission", "shared-key"),
        ).fetchall()
    assert len(rows) == 2
    assert sum(row[1] is not None for row in rows) == 1, (
        "One consume_effect call must not consume multiple independent actions"
    )
