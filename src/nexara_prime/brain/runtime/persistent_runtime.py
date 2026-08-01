"""Durable Persistent Runtime — SQLite-backed checkpoint, idempotency, recovery.

P1-006: Replaces process-local dict-based StateManager with atomic,
transactional SQLite persistence. Survives process restart.

Schema:
  checkpoints: mission_id, run_id, trace_id, state, step_index, data (JSON),
               completed_actions (JSON), pending_actions (JSON),
               idempotency_keys (JSON), evidence_head, created_at, updated_at
  idempotency: project_id, mission_id, action, idempotency_key (UNIQUE),
               effect_hash, created_at, consumed_at
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexara_prime.models import new_id, now_iso


class RuntimeState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERING = "recovering"


DEFAULT_DB_PATH = "runtime/nexara_durable.db"


@dataclass
class Checkpoint:
    checkpoint_id: str
    mission_id: str
    project_id: str
    run_id: str
    trace_id: str
    state: str
    step_index: int
    completed_actions: list[str] = field(default_factory=list)
    pending_actions: list[str] = field(default_factory=list)
    idempotency_keys: list[str] = field(default_factory=list)
    evidence_head: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    schema_version: int = 1


class StateManager:
    """Durable state manager with SQLite-backed checkpoint persistence.

    Survives process restart. Uses WAL mode, atomic transactions,
    and explicit busy timeout for concurrency safety.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize schema with migrations."""
        with self._lock:
            conn = self._get_conn()
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    step_index INTEGER NOT NULL DEFAULT 0,
                    completed_actions TEXT NOT NULL DEFAULT '[]',
                    pending_actions TEXT NOT NULL DEFAULT '[]',
                    idempotency_keys TEXT NOT NULL DEFAULT '[]',
                    evidence_head TEXT NOT NULL DEFAULT '',
                    data TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    schema_version INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS idempotency (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    effect_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    consumed_at TEXT,
                    UNIQUE(project_id, mission_id, action, idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS idx_checkpoints_mission
                    ON checkpoints(mission_id, project_id);
                CREATE INDEX IF NOT EXISTS idx_idempotency_lookup
                    ON idempotency(project_id, mission_id, idempotency_key);
            """)
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    # ── Checkpoint Operations ────────────────────────────────────────────────

    def save_checkpoint(self, cp: Checkpoint) -> str:
        """Atomically save a checkpoint. Returns checkpoint_id."""
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO checkpoints
                       (checkpoint_id, mission_id, project_id, run_id, trace_id,
                        state, step_index, completed_actions, pending_actions,
                        idempotency_keys, evidence_head, data, created_at, updated_at, schema_version)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        cp.checkpoint_id, cp.mission_id, cp.project_id, cp.run_id, cp.trace_id,
                        cp.state, cp.step_index,
                        json.dumps(cp.completed_actions), json.dumps(cp.pending_actions),
                        json.dumps(cp.idempotency_keys), cp.evidence_head,
                        json.dumps(cp.data), cp.created_at, now_iso(), cp.schema_version,
                    ),
                )
                conn.commit()
                return cp.checkpoint_id
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def load_checkpoint(self, mission_id: str, project_id: str) -> Checkpoint | None:
        """Load the latest checkpoint for a mission+project pair."""
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    """SELECT checkpoint_id, mission_id, project_id, run_id, trace_id,
                              state, step_index, completed_actions, pending_actions,
                              idempotency_keys, evidence_head, data, created_at, updated_at, schema_version
                       FROM checkpoints
                       WHERE mission_id=? AND project_id=?
                       ORDER BY updated_at DESC LIMIT 1""",
                    (mission_id, project_id),
                ).fetchone()
                if row is None:
                    return None
                return Checkpoint(
                    checkpoint_id=row[0], mission_id=row[1], project_id=row[2],
                    run_id=row[3], trace_id=row[4], state=row[5], step_index=row[6],
                    completed_actions=json.loads(row[7]), pending_actions=json.loads(row[8]),
                    idempotency_keys=json.loads(row[9]), evidence_head=row[10],
                    data=json.loads(row[11]), created_at=row[12], updated_at=row[13],
                    schema_version=row[14],
                )
            finally:
                conn.close()

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("DELETE FROM checkpoints WHERE checkpoint_id=?", (checkpoint_id,))
                conn.commit()
                return conn.total_changes > 0
            finally:
                conn.close()

    def list_checkpoints(self, project_id: str) -> list[Checkpoint]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    """SELECT checkpoint_id, mission_id, project_id, run_id, trace_id,
                              state, step_index, completed_actions, pending_actions,
                              idempotency_keys, evidence_head, data, created_at, updated_at, schema_version
                       FROM checkpoints WHERE project_id=? ORDER BY updated_at DESC""",
                    (project_id,),
                ).fetchall()
                return [
                    Checkpoint(
                        checkpoint_id=r[0], mission_id=r[1], project_id=r[2],
                        run_id=r[3], trace_id=r[4], state=r[5], step_index=r[6],
                        completed_actions=json.loads(r[7]), pending_actions=json.loads(r[8]),
                        idempotency_keys=json.loads(r[9]), evidence_head=r[10],
                        data=json.loads(r[11]), created_at=r[12], updated_at=r[13],
                        schema_version=r[14],
                    )
                    for r in rows
                ]
            finally:
                conn.close()

    # ── Idempotency ──────────────────────────────────────────────────────────

    def is_duplicate(self, project_id: str, mission_id: str, action: str, idempotency_key: str) -> bool:
        """Check if an idempotency key has already been consumed."""
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    "SELECT 1 FROM idempotency WHERE project_id=? AND mission_id=? AND action=? AND idempotency_key=?",
                    (project_id, mission_id, action, idempotency_key),
                ).fetchone()
                return row is not None
            finally:
                conn.close()

    def record_effect(self, project_id: str, mission_id: str, action: str, idempotency_key: str, effect_hash: str) -> bool:
        """Record a side effect. Returns False if duplicate (idempotency violation)."""
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT INTO idempotency (project_id, mission_id, action, idempotency_key, effect_hash, created_at)
                       VALUES (?,?,?,?,?,?)""",
                    (project_id, mission_id, action, idempotency_key, effect_hash, now_iso()),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # UNIQUE constraint violation = duplicate
                conn.rollback()
                return False
            finally:
                conn.close()

    def consume_effect(self, project_id: str, mission_id: str, idempotency_key: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "UPDATE idempotency SET consumed_at=? WHERE project_id=? AND mission_id=? AND idempotency_key=?",
                    (now_iso(), project_id, mission_id, idempotency_key),
                )
                conn.commit()
                return conn.total_changes > 0
            finally:
                conn.close()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            conn = self._get_conn()
            try:
                cp_count = conn.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
                id_count = conn.execute("SELECT COUNT(*) FROM idempotency").fetchone()[0]
                return {"checkpoints": cp_count, "idempotency_records": id_count}
            finally:
                conn.close()

    def close(self) -> None:
        """Clean shutdown — finalizes WAL and closes connections."""
        with self._lock:
            conn = self._get_conn()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()


class RecoveryEngine:
    """Recovers mission state from durable checkpoints after process restart."""

    def __init__(self, state_manager: StateManager) -> None:
        self._sm = state_manager
        self._attempts: list[dict[str, Any]] = []

    def can_recover(self, mission_id: str, project_id: str) -> bool:
        cp = self._sm.load_checkpoint(mission_id, project_id)
        return cp is not None

    def recover(self, mission_id: str, project_id: str) -> Checkpoint | None:
        cp = self._sm.load_checkpoint(mission_id, project_id)
        if cp is None:
            self._attempts.append({
                "mission_id": mission_id, "project_id": project_id,
                "result": "no_checkpoint", "timestamp": now_iso(),
            })
            return None
        self._attempts.append({
            "mission_id": mission_id, "project_id": project_id,
            "checkpoint_id": cp.checkpoint_id, "state": cp.state,
            "result": "recovered", "timestamp": now_iso(),
        })
        return cp

    def recover_or_fail(self, mission_id: str, project_id: str) -> Checkpoint:
        """Fail-closed: raise if no checkpoint available."""
        cp = self.recover(mission_id, project_id)
        if cp is None:
            raise RuntimeError(f"recovery_failed: no checkpoint for {project_id}/{mission_id}")
        return cp

    def attempts(self) -> list[dict[str, Any]]:
        return list(self._attempts)
