from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class SQLiteStore:
    """Small durable store for the modular-monolith MVP.

    Records carry an integrity envelope over identity, type, mission binding,
    creation time, and canonical payload. The store also exposes an atomic
    compare-and-set helper used for single-action approval consumption.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    @staticmethod
    def _canonical_payload(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _record_integrity(
        cls,
        record_id: str,
        record_type: str,
        mission_id: str | None,
        created_at: str,
        payload: dict[str, Any],
    ) -> str:
        envelope = {
            "record_id": record_id,
            "record_type": record_type,
            "mission_id": mission_id,
            "created_at": created_at,
            "payload": payload,
        }
        encoded = json.dumps(
            envelope,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _evidence_envelope_integrity(payload: dict[str, Any]) -> str:
        envelope = {
            "evidence_id": payload.get("evidence_id"),
            "mission_id": payload.get("mission_id"),
            "kind": payload.get("kind"),
            "sha256": payload.get("sha256"),
            "task_id": payload.get("task_id"),
            "tool_invocation_id": payload.get("tool_invocation_id"),
            "actor": payload.get("actor"),
            "source": payload.get("source"),
            "source_event_id": payload.get("source_event_id"),
            "verification_status": payload.get("verification_status"),
            "request_sha256": payload.get("request_sha256"),
        }
        encoded = json.dumps(
            envelope,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS records (
                    record_id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    mission_id TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    integrity_sha256 TEXT
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
            record_columns = {
                row[1] for row in self._conn.execute("PRAGMA table_info(records)").fetchall()
            }
            integrity_column_preexisted = "integrity_sha256" in record_columns
            if not integrity_column_preexisted:
                self._conn.execute("ALTER TABLE records ADD COLUMN integrity_sha256 TEXT")
            legacy_rows = self._conn.execute(
                "SELECT record_id, record_type, mission_id, payload, created_at, "
                "integrity_sha256 FROM records"
            ).fetchall()
            for row in legacy_rows:
                payload = json.loads(row["payload"])
                if integrity_column_preexisted and not row["integrity_sha256"]:
                    continue
                payload_changed = False
                if row["record_type"] == "evidence" and not payload.get("envelope_sha256"):
                    if row["integrity_sha256"]:
                        legacy_integrity = self._record_integrity(
                            row["record_id"],
                            row["record_type"],
                            row["mission_id"],
                            row["created_at"],
                            payload,
                        )
                        if row["integrity_sha256"] != legacy_integrity:
                            continue
                    payload["envelope_sha256"] = self._evidence_envelope_integrity(payload)
                    payload_changed = True
                if not payload_changed and row["integrity_sha256"]:
                    continue
                integrity = self._record_integrity(
                    row["record_id"],
                    row["record_type"],
                    row["mission_id"],
                    row["created_at"],
                    payload,
                )
                self._conn.execute(
                    "UPDATE records SET payload=?, integrity_sha256=? WHERE record_id=?",
                    (self._canonical_payload(payload), integrity, row["record_id"]),
                )
            event_columns = {
                row[1] for row in self._conn.execute("PRAGMA table_info(events)").fetchall()
            }
            if "idempotency_key" not in event_columns:
                self._conn.execute("ALTER TABLE events ADD COLUMN idempotency_key TEXT")
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_events_idempotency "
                "ON events(idempotency_key) WHERE idempotency_key IS NOT NULL"
            )

    def save_record(
        self,
        record_id: str,
        record_type: str,
        payload: dict[str, Any],
        created_at: str,
        mission_id: str | None = None,
    ) -> None:
        canonical = self._canonical_payload(payload)
        integrity = self._record_integrity(
            record_id, record_type, mission_id, created_at, payload
        )
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT INTO records(
                       record_id, record_type, mission_id, payload, created_at, integrity_sha256
                   ) VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(record_id) DO UPDATE SET
                       payload=excluded.payload,
                       mission_id=excluded.mission_id,
                       record_type=excluded.record_type,
                       created_at=excluded.created_at,
                       integrity_sha256=excluded.integrity_sha256""",
                (record_id, record_type, mission_id, canonical, created_at, integrity),
            )

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM records WHERE record_id=?", (record_id,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def save_record_if_absent(
        self,
        record_id: str,
        record_type: str,
        payload: dict[str, Any],
        created_at: str,
        mission_id: str | None = None,
    ) -> bool:
        """Insert an immutable first-write record without overwriting a winner."""
        canonical = self._canonical_payload(payload)
        integrity = self._record_integrity(
            record_id, record_type, mission_id, created_at, payload
        )
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO records("
                "record_id, record_type, mission_id, payload, created_at, integrity_sha256"
                ") VALUES (?, ?, ?, ?, ?, ?)",
                (record_id, record_type, mission_id, canonical, created_at, integrity),
            )
            return cursor.rowcount == 1

    def get_record_envelope(self, record_id: str) -> dict[str, Any] | None:
        """Return a record only when its persisted identity envelope is intact."""
        with self._lock:
            row = self._conn.execute(
                "SELECT record_id, record_type, mission_id, payload, created_at, "
                "integrity_sha256 FROM records WHERE record_id=?",
                (record_id,),
            ).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload"])
        expected = self._record_integrity(
            row["record_id"],
            row["record_type"],
            row["mission_id"],
            row["created_at"],
            payload,
        )
        if not row["integrity_sha256"] or row["integrity_sha256"] != expected:
            return None
        return {
            "record_id": row["record_id"],
            "record_type": row["record_type"],
            "mission_id": row["mission_id"],
            "created_at": row["created_at"],
            "integrity_sha256": row["integrity_sha256"],
            "payload": payload,
        }

    def compare_and_set_record_field(
        self,
        record_id: str,
        *,
        record_type: str,
        field: str,
        expected_value: Any,
        new_value: Any,
    ) -> dict[str, Any] | None:
        """Atomically update one payload field when the persisted value matches."""
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT record_id, record_type, mission_id, payload, created_at, "
                "integrity_sha256 FROM records WHERE record_id=? AND record_type=?",
                (record_id, record_type),
            ).fetchone()
            if not row:
                return None
            payload = json.loads(row["payload"])
            integrity = self._record_integrity(
                row["record_id"],
                row["record_type"],
                row["mission_id"],
                row["created_at"],
                payload,
            )
            if not row["integrity_sha256"] or row["integrity_sha256"] != integrity:
                return None
            if payload.get(field) != expected_value:
                return None
            payload[field] = new_value
            canonical = self._canonical_payload(payload)
            new_integrity = self._record_integrity(
                row["record_id"],
                row["record_type"],
                row["mission_id"],
                row["created_at"],
                payload,
            )
            cursor = self._conn.execute(
                "UPDATE records SET payload=?, integrity_sha256=? "
                "WHERE record_id=? AND record_type=? AND integrity_sha256=?",
                (
                    canonical,
                    new_integrity,
                    record_id,
                    record_type,
                    row["integrity_sha256"],
                ),
            )
            if cursor.rowcount != 1:
                return None
            return payload

    def replace_record_payload_if_integrity_matches(
        self,
        record_id: str,
        *,
        record_type: str,
        expected_integrity_sha256: str,
        new_payload: dict[str, Any],
    ) -> bool:
        """Replace a complete payload only if the exact validated record remains."""
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT record_id, record_type, mission_id, payload, created_at, "
                "integrity_sha256 FROM records WHERE record_id=? AND record_type=?",
                (record_id, record_type),
            ).fetchone()
            if not row or row["integrity_sha256"] != expected_integrity_sha256:
                return False
            current_payload = json.loads(row["payload"])
            current_integrity = self._record_integrity(
                row["record_id"],
                row["record_type"],
                row["mission_id"],
                row["created_at"],
                current_payload,
            )
            if current_integrity != expected_integrity_sha256:
                return False
            canonical = self._canonical_payload(new_payload)
            new_integrity = self._record_integrity(
                row["record_id"],
                row["record_type"],
                row["mission_id"],
                row["created_at"],
                new_payload,
            )
            cursor = self._conn.execute(
                "UPDATE records SET payload=?, integrity_sha256=? "
                "WHERE record_id=? AND record_type=? AND integrity_sha256=?",
                (
                    canonical,
                    new_integrity,
                    record_id,
                    record_type,
                    expected_integrity_sha256,
                ),
            )
            return cursor.rowcount == 1

    def compare_and_set_record_fields_atomically(
        self,
        updates: list[dict[str, Any]],
    ) -> bool:
        """Apply multiple record field transitions in one SQLite transaction.

        Every record must have a valid integrity envelope and every expected
        value must still match. If any precondition fails, no record is
        changed. This is used when one governed action consumes more than one
        approval (for example an R4 promotion plus its release approval).
        """
        if not updates:
            return True
        record_ids = [str(item["record_id"]) for item in updates]
        if len(record_ids) != len(set(record_ids)):
            return False

        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                prepared: list[tuple[str, str, str, str, str]] = []
                for item in updates:
                    record_id = str(item["record_id"])
                    record_type = str(item["record_type"])
                    field = str(item["field"])
                    row = self._conn.execute(
                        "SELECT record_id, record_type, mission_id, payload, "
                        "created_at, integrity_sha256 FROM records "
                        "WHERE record_id=? AND record_type=?",
                        (record_id, record_type),
                    ).fetchone()
                    if not row:
                        self._conn.rollback()
                        return False

                    payload = json.loads(row["payload"])
                    current_integrity = self._record_integrity(
                        row["record_id"],
                        row["record_type"],
                        row["mission_id"],
                        row["created_at"],
                        payload,
                    )
                    if (
                        not row["integrity_sha256"]
                        or row["integrity_sha256"] != current_integrity
                        or (
                            item.get("expected_integrity_sha256") is not None
                            and row["integrity_sha256"]
                            != item["expected_integrity_sha256"]
                        )
                        or payload.get(field) != item["expected_value"]
                    ):
                        self._conn.rollback()
                        return False

                    payload[field] = item["new_value"]
                    canonical = self._canonical_payload(payload)
                    new_integrity = self._record_integrity(
                        row["record_id"],
                        row["record_type"],
                        row["mission_id"],
                        row["created_at"],
                        payload,
                    )
                    prepared.append(
                        (
                            canonical,
                            new_integrity,
                            record_id,
                            record_type,
                            row["integrity_sha256"],
                        )
                    )

                for canonical, integrity, record_id, record_type, previous in prepared:
                    cursor = self._conn.execute(
                        "UPDATE records SET payload=?, integrity_sha256=? "
                        "WHERE record_id=? AND record_type=? AND integrity_sha256=?",
                        (canonical, integrity, record_id, record_type, previous),
                    )
                    if cursor.rowcount != 1:
                        self._conn.rollback()
                        return False
                self._conn.commit()
                return True
            except Exception:
                self._conn.rollback()
                raise

    def list_records(
        self, record_type: str, mission_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT payload FROM records WHERE record_type=?"
        params: list[Any] = [record_type]
        if mission_id:
            query += " AND mission_id=?"
            params.append(mission_id)
        query += " ORDER BY created_at ASC"
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def list_record_envelopes(
        self, record_type: str, mission_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = (
            "SELECT record_id FROM records WHERE record_type=?"
            + (" AND mission_id=?" if mission_id else "")
            + " ORDER BY created_at ASC"
        )
        params: list[Any] = [record_type]
        if mission_id:
            params.append(mission_id)
        with self._lock:
            ids = [row["record_id"] for row in self._conn.execute(query, params)]
        envelopes: list[dict[str, Any]] = []
        for record_id in ids:
            envelope = self.get_record_envelope(record_id)
            if not envelope:
                raise ValueError(f"record_integrity_invalid:{record_id}")
            envelopes.append(envelope)
        return envelopes

    def audit_record_envelopes(
        self, record_type: str, mission_id: str | None = None
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Enumerate valid and corrupt records without trusting mission metadata.

        Mission-scoped audits include rows selected by either the stored mission
        column or the payload mission, so moving only one side cannot hide a
        damaged record from completion checks.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT record_id, mission_id, payload FROM records "
                "WHERE record_type=? ORDER BY created_at ASC",
                (record_type,),
            ).fetchall()
        valid: list[dict[str, Any]] = []
        invalid: list[str] = []
        for row in rows:
            try:
                payload = json.loads(row["payload"])
            except (TypeError, ValueError):
                payload = {}
            if mission_id is not None and (
                row["mission_id"] != mission_id
                and payload.get("mission_id") != mission_id
            ):
                continue
            envelope = self.get_record_envelope(row["record_id"])
            if envelope is None:
                invalid.append(str(row["record_id"]))
            else:
                valid.append(envelope)
        return valid, invalid

    def save_event(self, event: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT OR IGNORE INTO events(event_id, event_type, aggregate_id, aggregate_type,
                   actor, trace_id, timestamp, idempotency_key, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event["event_id"], event["event_type"], event["aggregate_id"],
                    event["aggregate_type"], event["actor"], event["trace_id"],
                    event["timestamp"], event.get("idempotency_key"),
                    json.dumps(event.get("payload", {}), ensure_ascii=False),
                ),
            )
            if event.get("idempotency_key"):
                row = self._conn.execute(
                    "SELECT * FROM events WHERE idempotency_key=?",
                    (event["idempotency_key"],),
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT * FROM events WHERE event_id=?", (event["event_id"],)
                ).fetchone()
        if not row:
            raise RuntimeError("event_persistence_failed")
        persisted = dict(row)
        persisted["payload"] = json.loads(persisted["payload"])
        return persisted

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM events WHERE event_id=?", (event_id,)
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["payload"] = json.loads(item["payload"])
        return item

    def get_event_by_idempotency(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM events WHERE idempotency_key=?", (key,)
            ).fetchone()
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
