"""BrainDB — isolated SQLite database for brain memory persistence.

DEPRECATED as standalone DB manager (v1.0.0 F1 consolidation).
Connection/threading/schema management delegated to canonical SQLiteStore
(src/nexara_prime/db.py) — the single DB authority.

BrainDB retains brain-specific table schema and semantic CRUD methods.

Migration path: prefer MemoryController public API; for direct DB access
use SQLiteStore from nexara_prime.db.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..db import SQLiteStore
from ..models import now_iso, new_id


BRAIN_STATE_PATH = Path(".nexara/brain_state.db")

# Brain-specific DDL — previously loaded from schemas/brain_state_schema.sql.
# Inlined here so BrainDB only adds brain tables on top of SQLiteStore's base.
_BRAIN_DDL = """
CREATE TABLE IF NOT EXISTS brain_memories (
    memory_id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL DEFAULT 'global',
    key TEXT NOT NULL,
    content TEXT NOT NULL,
    kind TEXT NOT NULL,
    layer TEXT NOT NULL DEFAULT 'semantic',
    confidence REAL NOT NULL DEFAULT 1.0,
    decay_rate REAL NOT NULL DEFAULT 0.0,
    half_life_seconds INTEGER,
    evidence_id TEXT,
    provenance_chain TEXT,
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed TEXT,
    consolidated_from TEXT,
    superseded_by TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_brain_memories_mission ON brain_memories(mission_id);
CREATE INDEX IF NOT EXISTS idx_brain_memories_kind ON brain_memories(kind);
CREATE INDEX IF NOT EXISTS idx_brain_memories_layer ON brain_memories(layer);
CREATE INDEX IF NOT EXISTS idx_brain_memories_key ON brain_memories(key);
CREATE INDEX IF NOT EXISTS idx_brain_memories_status ON brain_memories(status);
CREATE TABLE IF NOT EXISTS memory_decay_state (
    kind TEXT PRIMARY KEY,
    half_life_seconds INTEGER NOT NULL,
    min_confidence REAL NOT NULL DEFAULT 0.1,
    decay_function TEXT NOT NULL DEFAULT 'exponential',
    last_tick TEXT,
    updated_at TEXT NOT NULL
);
INSERT OR IGNORE INTO memory_decay_state(kind, half_life_seconds, min_confidence) VALUES
    ('short_term', 3600, 0.1),
    ('temporary_context', 86400, 0.1),
    ('unverified_inference', 1800, 0.05),
    ('fact', 7776000, 0.3),
    ('user_fact', 15552000, 0.5),
    ('project_fact', 31536000, 0.5),
    ('preference', 7776000, 0.3),
    ('decision', 0, 0.9),
    ('failure', 0, 0.9),
    ('failure_experience', 15552000, 0.3),
    ('patch', 0, 0.9),
    ('skill_improvement', 0, 0.9),
    ('system_rule', 0, 0.9);
CREATE TABLE IF NOT EXISTS memory_consolidation_log (
    log_id TEXT PRIMARY KEY,
    source_memory_id TEXT NOT NULL,
    target_memory_id TEXT NOT NULL,
    from_layer TEXT NOT NULL,
    to_layer TEXT NOT NULL,
    trigger TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_access_log (
    log_id TEXT PRIMARY KEY,
    memory_id TEXT NOT NULL,
    accessed_at TEXT NOT NULL,
    query TEXT,
    access_type TEXT NOT NULL DEFAULT 'recall'
);
CREATE INDEX IF NOT EXISTS idx_access_log_memory ON memory_access_log(memory_id);
CREATE TABLE IF NOT EXISTS memory_health_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    total_memories INTEGER NOT NULL DEFAULT 0,
    active_count INTEGER NOT NULL DEFAULT 0,
    stale_count INTEGER NOT NULL DEFAULT 0,
    archived_count INTEGER NOT NULL DEFAULT 0,
    coverage_score REAL NOT NULL DEFAULT 0.0,
    freshness_score REAL NOT NULL DEFAULT 0.0,
    consistency_score REAL NOT NULL DEFAULT 0.0,
    layer_distribution TEXT NOT NULL DEFAULT '{}',
    kind_distribution TEXT NOT NULL DEFAULT '{}',
    taken_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_provenance_chain (
    provenance_id TEXT PRIMARY KEY,
    memory_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    source_file TEXT,
    commit_sha TEXT,
    trace_id TEXT,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_provenance_memory ON memory_provenance_chain(memory_id);
CREATE INDEX IF NOT EXISTS idx_provenance_evidence ON memory_provenance_chain(evidence_id);
"""


class BrainDB:
    """Manages brain_state.db — connection mgmt delegated to SQLiteStore.

    DEPRECATED: This is a compatibility wrapper. SQLiteStore (nexara_prime.db)
    is the single DB authority for ALL SQLite initialization, connection
    management, threading, and schema creation.

    BrainDB retains brain-specific table schema and semantic methods
    (recall, consolidation, decay, provenance, health).
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else BRAIN_STATE_PATH
        # Delegate ALL connection/threading/schema management to canonical
        # SQLiteStore — the single DB authority for the project.
        self._store = SQLiteStore(self.path)
        # Add brain-specific tables on top of SQLiteStore's base schema.
        # SQLiteStore._init_schema() already created records + events tables;
        # brain tables are additive and use separate namespace.
        self._store._conn.executescript(_BRAIN_DDL)
        self._store._conn.commit()
        # Convenience refs so existing method bodies remain unchanged.
        self._conn = self._store._conn
        self._lock = self._store._lock

    # ── Memory CRUD ──

    def insert_memory(self, record: dict[str, Any]) -> str:
        memory_id = record.get("memory_id") or new_id("mem")
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO brain_memories
                   (memory_id, mission_id, key, content, kind, layer, confidence,
                    decay_rate, half_life_seconds, evidence_id, provenance_chain,
                    access_count, last_accessed, consolidated_from, superseded_by,
                    status, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    memory_id,
                    record.get("mission_id", "global"),
                    record.get("key", ""),
                    record.get("content", ""),
                    record.get("kind", "fact"),
                    record.get("layer", "semantic"),
                    record.get("confidence", 1.0),
                    record.get("decay_rate", 0.0),
                    record.get("half_life_seconds"),
                    record.get("evidence_id"),
                    record.get("provenance_chain"),
                    record.get("access_count", 0),
                    record.get("last_accessed"),
                    record.get("consolidated_from"),
                    record.get("superseded_by"),
                    record.get("status", "active"),
                    record.get("created_at", now_iso()),
                    record.get("updated_at"),
                ),
            )
            self._conn.commit()
        return memory_id

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM brain_memories WHERE memory_id = ?", (memory_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_memory_by_key(self, key: str, mission_id: str = "global") -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM brain_memories WHERE key = ? AND mission_id = ? AND status = 'active' ORDER BY created_at DESC",
            (key, mission_id),
        ).fetchall()
        return [dict(r) for r in rows]

    def recall(
        self,
        mission_id: str | None = None,
        layer: str | None = None,
        kind: str | None = None,
        status: str = "active",
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM brain_memories WHERE status = ?"
        params: list[Any] = [status]
        if mission_id:
            query += " AND mission_id = ?"
            params.append(mission_id)
        if layer:
            query += " AND layer = ?"
            params.append(layer)
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        query += " ORDER BY created_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def update_memory(self, memory_id: str, updates: dict[str, Any]) -> bool:
        if not updates:
            return False
        updates["updated_at"] = now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [memory_id]
        with self._lock:
            self._conn.execute(
                f"UPDATE brain_memories SET {set_clause} WHERE memory_id = ?", values
            )
            self._conn.commit()
        return True

    def update_status(self, memory_id: str, status: str) -> bool:
        return self.update_memory(memory_id, {"status": status})

    # ── Decay ──

    def get_decay_config(self, kind: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM memory_decay_state WHERE kind = ?", (kind,)
        ).fetchone()
        return dict(row) if row else None

    def get_all_decay_configs(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM memory_decay_state").fetchall()
        return [dict(r) for r in rows]

    # ── Consolidation Log ──

    def log_consolidation(
        self, source_id: str, target_id: str, from_layer: str, to_layer: str,
        trigger: str, reason: str = "",
    ) -> str:
        log_id = new_id("consol")
        self._conn.execute(
            """INSERT INTO memory_consolidation_log
               (log_id, source_memory_id, target_memory_id, from_layer, to_layer, trigger, reason, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (log_id, source_id, target_id, from_layer, to_layer, trigger, reason, now_iso()),
        )
        self._conn.commit()
        return log_id

    # ── Access Log ──

    def log_access(self, memory_id: str, access_type: str = "recall", query: str = "") -> str:
        log_id = new_id("acc")
        self._conn.execute(
            "INSERT INTO memory_access_log (log_id, memory_id, accessed_at, query, access_type) VALUES (?,?,?,?,?)",
            (log_id, memory_id, now_iso(), query, access_type),
        )
        self._conn.commit()
        return log_id

    # ── Health ──

    def save_health_snapshot(self, snapshot: dict[str, Any]) -> str:
        sid = snapshot.get("snapshot_id") or new_id("health")
        self._conn.execute(
            """INSERT INTO memory_health_snapshots
               (snapshot_id, total_memories, active_count, stale_count, archived_count,
                coverage_score, freshness_score, consistency_score, layer_distribution, kind_distribution, taken_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                sid,
                snapshot.get("total_memories", 0),
                snapshot.get("active_count", 0),
                snapshot.get("stale_count", 0),
                snapshot.get("archived_count", 0),
                snapshot.get("coverage_score", 0.0),
                snapshot.get("freshness_score", 0.0),
                snapshot.get("consistency_score", 0.0),
                json.dumps(snapshot.get("layer_distribution", {})),
                json.dumps(snapshot.get("kind_distribution", {})),
                snapshot.get("taken_at", now_iso()),
            ),
        )
        self._conn.commit()
        return sid

    def get_latest_health_snapshot(self) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM memory_health_snapshots ORDER BY taken_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    # ── Provenance ──

    def record_provenance(
        self, memory_id: str, evidence_id: str,
        source_file: str = "", commit_sha: str = "", trace_id: str = "",
    ) -> str:
        pid = new_id("prov")
        self._conn.execute(
            """INSERT OR REPLACE INTO memory_provenance_chain
               (provenance_id, memory_id, evidence_id, source_file, commit_sha, trace_id, recorded_at)
               VALUES (?,?,?,?,?,?,?)""",
            (pid, memory_id, evidence_id, source_file, commit_sha, trace_id, now_iso()),
        )
        self._conn.commit()
        return pid

    def get_provenance(self, memory_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM memory_provenance_chain WHERE memory_id = ?", (memory_id,)
        ).fetchone()
        return dict(row) if row else None

    # ── Stats ──

    def count_by_layer(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT layer, COUNT(*) as cnt FROM brain_memories WHERE status = 'active' GROUP BY layer"
        ).fetchall()
        return {r["layer"]: r["cnt"] for r in rows}

    def count_by_kind(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT kind, COUNT(*) as cnt FROM brain_memories WHERE status = 'active' GROUP BY kind"
        ).fetchall()
        return {r["kind"]: r["cnt"] for r in rows}

    def count_active(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM brain_memories WHERE status = 'active'"
        ).fetchone()
        return row["cnt"] if row else 0

    def count_stale(self, stale_threshold_seconds: int = 86400) -> int:
        row = self._conn.execute(
            """SELECT COUNT(*) as cnt FROM brain_memories
               WHERE status = 'active' AND confidence < 0.3
               AND (last_accessed IS NULL OR last_accessed < ?)""",
            (now_iso(),),
        ).fetchone()
        return row["cnt"] if row else 0

    def close(self) -> None:
        self._conn.close()
