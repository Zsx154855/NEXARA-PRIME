"""Durable, fenced task ledger for the NEXARA R&D factory.

The ledger is the single source of truth for who owns a task. Ownership is
carried by an attempt token plus a monotonically increasing epoch, so a worker
whose lease expired can never land a receipt or a terminal result after a newer
attempt exists.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ACTIVE_STATES = ("claimed", "running", "verifying")
TERMINAL_STATES = ("delivered", "failed", "blocked", "cancelled")
ALL_STATES = ("queued",) + ACTIVE_STATES + TERMINAL_STATES


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class LedgerError(RuntimeError):
    """Contract violation inside the task ledger."""


class FenceError(LedgerError):
    """A write lost the race against a newer attempt of the same task."""


class BudgetExhausted(LedgerError):
    """The task consumed every attempt its budget allows."""


@dataclass(frozen=True)
class Claim:
    task_id: str
    title: str
    objective: str
    acceptance: list[str]
    scope: list[str]
    attempt_token: str
    epoch: int
    attempts_used: int
    budget_attempts: int
    branch: str | None
    worktree: str | None

    @property
    def attempts_left(self) -> int:
        return max(0, self.budget_attempts - self.attempts_used)


@dataclass(frozen=True)
class TaskView:
    task_id: str
    title: str
    objective: str
    acceptance: list[str]
    scope: list[str]
    state: str
    epoch: int
    owner: str | None
    attempt_token: str | None
    lease_expires_at: str | None
    attempts_used: int
    budget_attempts: int
    pr_url: str | None
    last_error: str | None
    dedupe_key: str | None

    @property
    def lease_expired(self) -> bool:
        if not self.lease_expires_at:
            return True
        return datetime.fromisoformat(self.lease_expires_at) < utc_now()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    dedupe_key TEXT UNIQUE,
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    acceptance TEXT NOT NULL DEFAULT '[]',
    scope TEXT NOT NULL DEFAULT '[]',
    state TEXT NOT NULL DEFAULT 'queued',
    epoch INTEGER NOT NULL DEFAULT 0,
    attempt_token TEXT,
    owner TEXT,
    lease_expires_at TEXT,
    budget_attempts INTEGER NOT NULL DEFAULT 3,
    attempts_used INTEGER NOT NULL DEFAULT 0,
    branch TEXT,
    worktree TEXT,
    pr_url TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    attempt_token TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    epoch INTEGER NOT NULL,
    worker TEXT NOT NULL,
    state TEXT NOT NULL,
    exit_code INTEGER,
    started_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS receipts (
    receipt_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    attempt_token TEXT NOT NULL,
    epoch INTEGER NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_receipts_task ON receipts(task_id, epoch);
"""


class TaskLedger:
    """SQLite task ledger with atomic claim and epoch fencing."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=30000")
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # -- writes -------------------------------------------------------------
    def enqueue(
        self,
        *,
        title: str,
        objective: str,
        acceptance: list[str],
        scope: list[str],
        budget_attempts: int = 3,
        dedupe_key: str | None = None,
    ) -> str:
        now = iso(utc_now())
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        try:
            self._conn.execute(
                "INSERT INTO tasks (task_id, dedupe_key, title, objective, acceptance, scope,"
                " state, budget_attempts, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,'queued',?,?,?)",
                (
                    task_id,
                    dedupe_key,
                    title,
                    objective,
                    json.dumps(acceptance, ensure_ascii=False),
                    json.dumps(scope, ensure_ascii=False),
                    budget_attempts,
                    now,
                    now,
                ),
            )
        except sqlite3.IntegrityError as exc:
            existing = self._conn.execute(
                "SELECT task_id FROM tasks WHERE dedupe_key = ?", (dedupe_key,)
            ).fetchone()
            if existing is None:
                raise LedgerError(str(exc)) from exc
            return str(existing["task_id"])
        self._event(task_id, "task.enqueued", {"title": title})
        return task_id

    def claim(self, worker: str, ttl_seconds: int = 900) -> Claim | None:
        """Atomically take ownership of one eligible task, or return None."""
        now = utc_now()
        expires = iso(now + timedelta(seconds=ttl_seconds))
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT * FROM tasks WHERE attempts_used < budget_attempts AND ("
                " state = 'queued' OR (state IN ('claimed','running','verifying')"
                " AND lease_expires_at < ?)) ORDER BY created_at LIMIT 1",
                (iso(now),),
            ).fetchone()
            if row is None:
                self._conn.execute("COMMIT")
                return None
            token = f"att_{uuid.uuid4().hex}"
            epoch = int(row["epoch"]) + 1
            updated = self._conn.execute(
                "UPDATE tasks SET state='claimed', owner=?, attempt_token=?, epoch=?,"
                " lease_expires_at=?, attempts_used=attempts_used+1, last_error=NULL,"
                " updated_at=? WHERE task_id=? AND epoch=? AND attempts_used < budget_attempts",
                (worker, token, epoch, expires, iso(now), row["task_id"], int(row["epoch"])),
            )
            if updated.rowcount != 1:
                self._conn.execute("ROLLBACK")
                return None
            self._conn.execute(
                "INSERT INTO attempts (attempt_token, task_id, epoch, worker, state, started_at)"
                " VALUES (?,?,?,?, 'claimed', ?)",
                (token, row["task_id"], epoch, worker, iso(now)),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        self._event(row["task_id"], "task.claimed", {"worker": worker, "epoch": epoch})
        return Claim(
            task_id=str(row["task_id"]),
            title=str(row["title"]),
            objective=str(row["objective"]),
            acceptance=json.loads(row["acceptance"]),
            scope=json.loads(row["scope"]),
            attempt_token=token,
            epoch=epoch,
            attempts_used=int(row["attempts_used"]) + 1,
            budget_attempts=int(row["budget_attempts"]),
            branch=row["branch"],
            worktree=row["worktree"],
        )

    def renew(self, task_id: str, attempt_token: str, ttl_seconds: int = 900) -> None:
        now = utc_now()
        changed = self._conn.execute(
            "UPDATE tasks SET lease_expires_at=?, updated_at=? WHERE task_id=?"
            " AND attempt_token=? AND state IN ('claimed','running','verifying')",
            (iso(now + timedelta(seconds=ttl_seconds)), iso(now), task_id, attempt_token),
        )
        if changed.rowcount != 1:
            raise FenceError(f"renew rejected for {task_id}: attempt is not current")

    def mark_running(self, task_id: str, attempt_token: str, branch: str | None = None,
                     worktree: str | None = None) -> None:
        now = iso(utc_now())
        changed = self._conn.execute(
            "UPDATE tasks SET state='running', branch=COALESCE(?, branch),"
            " worktree=COALESCE(?, worktree), updated_at=? WHERE task_id=?"
            " AND attempt_token=? AND state IN ('claimed','running')",
            (branch, worktree, now, task_id, attempt_token),
        )
        if changed.rowcount != 1:
            raise FenceError(f"mark_running rejected for {task_id}: attempt is not current")
        self._conn.execute(
            "UPDATE attempts SET state='running' WHERE attempt_token=?", (attempt_token,)
        )
        self._event(task_id, "task.running", {"branch": branch, "worktree": worktree})

    def start_verification(self, task_id: str, attempt_token: str) -> None:
        now = iso(utc_now())
        changed = self._conn.execute(
            "UPDATE tasks SET state='verifying', updated_at=? WHERE task_id=?"
            " AND attempt_token=? AND state IN ('running','verifying')",
            (now, task_id, attempt_token),
        )
        if changed.rowcount != 1:
            raise FenceError(f"start_verification rejected for {task_id}")
        self._event(task_id, "task.verifying", {})

    def record_receipt(self, task_id: str, attempt_token: str, kind: str,
                       payload: dict[str, Any]) -> str:
        """Durably record evidence produced by the current attempt only."""
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        if row is None:
            raise LedgerError(f"unknown task {task_id}")
        if row["attempt_token"] != attempt_token:
            raise FenceError("stale receipt: attempt token is superseded")
        if row["state"] not in ACTIVE_STATES:
            raise FenceError(f"stale receipt: task is {row['state']}")
        receipt_id = f"rcp_{uuid.uuid4().hex[:12]}"
        self._conn.execute(
            "INSERT INTO receipts (receipt_id, task_id, attempt_token, epoch, kind, payload,"
            " recorded_at) VALUES (?,?,?,?,?,?,?)",
            (
                receipt_id,
                task_id,
                attempt_token,
                int(row["epoch"]),
                kind,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                iso(utc_now()),
            ),
        )
        self._event(task_id, f"receipt.{kind}", payload)
        return receipt_id

    def finish(self, task_id: str, attempt_token: str, state: str, *,
               pr_url: str | None = None, error: str | None = None,
               exit_code: int | None = None) -> None:
        if state not in TERMINAL_STATES:
            raise LedgerError(f"finish requires a terminal state, got {state}")
        now = iso(utc_now())
        changed = self._conn.execute(
            "UPDATE tasks SET state=?, pr_url=COALESCE(?, pr_url), last_error=?,"
            " updated_at=?, lease_expires_at=NULL, owner=NULL WHERE task_id=?"
            " AND attempt_token=? AND state IN ('claimed','running','verifying')",
            (state, pr_url, error, now, task_id, attempt_token),
        )
        if changed.rowcount != 1:
            raise FenceError(f"finish rejected for {task_id}: attempt is not current")
        self._conn.execute(
            "UPDATE attempts SET state=?, exit_code=?, finished_at=? WHERE attempt_token=?",
            (state, exit_code, now, attempt_token),
        )
        self._event(task_id, f"task.{state}", {"pr_url": pr_url, "error": error})

    def release(self, task_id: str, attempt_token: str, reason: str) -> None:
        """Hand a task back to the queue after a failed attempt that may retry."""
        now = iso(utc_now())
        changed = self._conn.execute(
            "UPDATE tasks SET state='queued', owner=NULL, attempt_token=NULL,"
            " lease_expires_at=NULL, epoch=epoch+1, last_error=?, updated_at=?"
            " WHERE task_id=? AND attempt_token=? AND state IN ('claimed','running','verifying')",
            (reason, now, task_id, attempt_token),
        )
        if changed.rowcount != 1:
            raise FenceError(f"release rejected for {task_id}: attempt is not current")
        self._conn.execute(
            "UPDATE attempts SET state='released', finished_at=? WHERE attempt_token=?",
            (now, attempt_token),
        )
        self._event(task_id, "task.released", {"reason": reason})

    def requeue_expired(self, now: datetime | None = None) -> list[str]:
        """Return every zombie attempt to the queue and fence its token off."""
        moment = now or utc_now()
        rows = self._conn.execute(
            "SELECT task_id, attempt_token FROM tasks WHERE state IN ('claimed','running','verifying')"
            " AND lease_expires_at IS NOT NULL AND lease_expires_at < ?",
            (iso(moment),),
        ).fetchall()
        requeued: list[str] = []
        for row in rows:
            changed = self._conn.execute(
                "UPDATE tasks SET state='queued', owner=NULL, attempt_token=NULL,"
                " lease_expires_at=NULL, epoch=epoch+1, updated_at=?,"
                " last_error=COALESCE(last_error, 'lease expired')"
                " WHERE task_id=? AND attempt_token=? AND state IN ('claimed','running','verifying')",
                (iso(moment), row["task_id"], row["attempt_token"]),
            )
            if changed.rowcount != 1:
                continue
            self._conn.execute(
                "UPDATE attempts SET state='orphaned', finished_at=? WHERE attempt_token=?",
                (iso(moment), row["attempt_token"]),
            )
            self._event(row["task_id"], "task.requeued", {"reason": "lease_expired"})
            requeued.append(str(row["task_id"]))
        return requeued

    def cancel(self, task_id: str, reason: str = "cancelled") -> None:
        """Cancel a queued or active task, failing closed on anything else.

        An unknown task id or a task already in a terminal state raises
        ``LedgerError`` and records no cancellation event, so the audit trail
        never claims a cancellation that did not actually happen.
        """
        now = iso(utc_now())
        changed = self._conn.execute(
            "UPDATE tasks SET state='cancelled', last_error=?, attempt_token=NULL,"
            " owner=NULL, lease_expires_at=NULL, updated_at=? WHERE task_id=?"
            " AND state IN ('queued','claimed','running','verifying')",
            (reason, now, task_id),
        )
        if changed.rowcount != 1:
            row = self._conn.execute(
                "SELECT state FROM tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if row is None:
                raise LedgerError(f"unknown task {task_id}")
            raise LedgerError(f"cannot cancel task {task_id}: task is {row['state']}")
        self._event(task_id, "task.cancelled", {"reason": reason})

    # -- reads --------------------------------------------------------------
    def get(self, task_id: str) -> TaskView:
        row = self._conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise LedgerError(f"unknown task {task_id}")
        return self._view(row)

    def list_tasks(self, state: str | None = None) -> list[TaskView]:
        if state:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE state=? ORDER BY created_at", (state,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM tasks ORDER BY created_at").fetchall()
        return [self._view(row) for row in rows]

    def receipts(self, task_id: str, attempt_token: str | None = None) -> list[dict[str, Any]]:
        if attempt_token:
            rows = self._conn.execute(
                "SELECT * FROM receipts WHERE task_id=? AND attempt_token=? ORDER BY recorded_at",
                (task_id, attempt_token),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM receipts WHERE task_id=? ORDER BY recorded_at", (task_id,)
            ).fetchall()
        return [
            {
                "receipt_id": row["receipt_id"],
                "attempt_token": row["attempt_token"],
                "epoch": row["epoch"],
                "kind": row["kind"],
                "payload": json.loads(row["payload"]),
                "recorded_at": row["recorded_at"],
            }
            for row in rows
        ]

    def attempts(self, task_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM attempts WHERE task_id=? ORDER BY epoch", (task_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def events(self, task_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if task_id:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE task_id=? ORDER BY seq DESC LIMIT ?", (task_id, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM events ORDER BY seq DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT state, COUNT(*) AS n FROM tasks GROUP BY state"
        ).fetchall()
        counts = {state: 0 for state in ALL_STATES}
        for row in rows:
            counts[str(row["state"])] = int(row["n"])
        return counts

    # -- internals ----------------------------------------------------------
    def _event(self, task_id: str | None, kind: str, detail: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO events (task_id, kind, detail, created_at) VALUES (?,?,?,?)",
            (task_id, kind, json.dumps(detail, ensure_ascii=False, default=str), iso(utc_now())),
        )

    @staticmethod
    def _view(row: sqlite3.Row) -> TaskView:
        return TaskView(
            task_id=str(row["task_id"]),
            title=str(row["title"]),
            objective=str(row["objective"]),
            acceptance=json.loads(row["acceptance"]),
            scope=json.loads(row["scope"]),
            state=str(row["state"]),
            epoch=int(row["epoch"]),
            owner=row["owner"],
            attempt_token=row["attempt_token"],
            lease_expires_at=row["lease_expires_at"],
            attempts_used=int(row["attempts_used"]),
            budget_attempts=int(row["budget_attempts"]),
            pr_url=row["pr_url"],
            last_error=row["last_error"],
            dedupe_key=row["dedupe_key"],
        )