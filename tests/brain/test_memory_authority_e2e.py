"""ADR-008 isolated end-to-end: one SQLiteStore hosts evidence + brain memory.

No Runtime wiring and no production database; this proves the adapter shape on a
throwaway file.
"""

from __future__ import annotations

import sqlite3

from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.experience_learner import ExperienceLearner
from nexara_prime.brain.memory_controller import MemoryController
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.models import ToolInvocation


def test_single_store_serves_evidence_and_experience(tmp_path):
    path = tmp_path / "authority.db"
    store = SQLiteStore(path)
    events = EventBus(store)
    evidence = EvidenceStore(store, events)
    brain = BrainDB(store=store)
    assert brain._conn is store._conn

    learner = ExperienceLearner(MemoryController(db=brain), evidence_store=evidence)
    invocation = ToolInvocation(
        mission_id="mission-A", tool_name="run_pytest", status="completed",
        result={"ok": True}, trace_id="trace-A",
    )
    receipt = evidence.add(
        "mission-A", "execution_receipt", "Tool receipt: run_pytest",
        invocation.model_dump_json(), invocation.trace_id,
        tool_invocation_id=invocation.invocation_id,
        actor="tool_runtime", source="tool_runtime",
        verification_status="verified",
    )
    learner.record_outcome(
        "mission-A", "success", "run_pytest", "ok", True,
        evidence_id=receipt.evidence_id,
    )
    assert len(learner.rank_experiences("run_pytest")) == 1

    with store._lock:
        tables = {
            row["name"]
            for row in store._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"records", "brain_memories", "brain_memory_idempotency"} <= tables

    # Independent connection sees the same single file; no side database.
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM brain_memories WHERE kind='experience'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type='evidence'"
        ).fetchone()[0] == 1
    assert not (tmp_path / ".nexara" / "brain_state.db").exists()
    store.close()


def test_reopening_same_store_keeps_one_authority(tmp_path):
    path = tmp_path / "authority.db"
    first = SQLiteStore(path)
    first.close()
    second = SQLiteStore(path)
    brain = BrainDB(store=second)
    assert brain.path == second.path
    assert brain._conn is second._conn
    second.close()
