from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class SQLiteStore:
    """Small durable store for the modular-monolith MVP."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS records (
                    record_id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    mission_id TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_records_type ON records(record_type);
                CREATE INDEX IF NOT EXISTS idx_records_mission ON records(mission_id);
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    aggregate_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_aggregate ON events(aggregate_id);
                """
            )
            columns = {row[1] for row in self._conn.execute("PRAGMA table_info(events)").fetchall()}
            if "idempotency_key" not in columns:
                self._conn.execute("ALTER TABLE events ADD COLUMN idempotency_key TEXT")
            self._conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_events_idempotency ON events(idempotency_key) WHERE idempotency_key IS NOT NULL")

    def save_record(self, record_id: str, record_type: str, payload: dict[str, Any], created_at: str, mission_id: str | None = None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT INTO records(record_id, record_type, mission_id, payload, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(record_id) DO UPDATE SET payload=excluded.payload, mission_id=excluded.mission_id""",
                (record_id, record_type, mission_id, json.dumps(payload, ensure_ascii=False), created_at),
            )

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT payload FROM records WHERE record_id=?", (record_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def compare_and_set_record_field(
        self,
        record_id: str,
        *,
        field: str,
        expected: Any,
        new_value: Any,
    ) -> bool:
        """Atomically update one JSON field when its current value matches expected."""
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT payload FROM records WHERE record_id=?",
                (record_id,),
            ).fetchone()
            if not row:
                return False
            payload = json.loads(row["payload"])
            if payload.get(field) != expected:
                return False
            payload[field] = new_value
            cursor = self._conn.execute(
                "UPDATE records SET payload=? WHERE record_id=? AND payload=?",
                (json.dumps(payload, ensure_ascii=False), record_id, row["payload"]),
            )
            return cursor.rowcount == 1

    def list_records(self, record_type: str, mission_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT payload FROM records WHERE record_type=?"
        params: list[Any] = [record_type]
        if mission_id:
            query += " AND mission_id=?"
            params.append(mission_id)
        query += " ORDER BY created_at ASC"
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def save_event(self, event: dict[str, Any]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT OR REPLACE INTO events(event_id, event_type, aggregate_id, aggregate_type,
                   actor, trace_id, timestamp, idempotency_key, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event["event_id"], event["event_type"], event["aggregate_id"], event["aggregate_type"],
                    event["actor"], event["trace_id"], event["timestamp"], event.get("idempotency_key"),
                    json.dumps(event.get("payload", {}), ensure_ascii=False),
                ),
            )

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["payload"] = json.loads(item["payload"])
        return item

    def get_event_by_idempotency(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM events WHERE idempotency_key=?", (key,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["payload"] = json.loads(item["payload"])
        return item

    def list_events(self, aggregate_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM events"
        params: list[Any] = []
        if aggregate_id:
            query += " WHERE aggregate_id=?"
            params.append(aggregate_id)
        query += " ORDER BY timestamp ASC"
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item["payload"])
            result.append(item)
        return result

    def find_record(self, record_type: str, field: str, value: Any) -> dict[str, Any] | None:
        """Small indexed-by-application helper used for idempotency in the MVP."""
        for item in self.list_records(record_type):
            if item.get(field) == value:
                return item
        return None

    def count(self, table: str) -> int:
        if table not in {"records", "events"}:
            raise ValueError("unsupported_count_table")
        with self._lock:
            return int(self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()
