"""Local P2 experiment using the relay SQLite and lease primitives.

The caller supplies a trusted local admission adapter. No network entry point or
production CAB binding is defined here. Never construct an adapter from a task.
"""

from dataclasses import dataclass
import os
import re
import uuid

from durable import Controller, digest, stopped
import relay


OPERATIONS = frozenset({"repo.inspect", "repo.apply_patch", "files.read", "files.write", "test.run", "dsh.task.run"})
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{2,79}")
TASK_KEYS = {"mission_id", "task_id", "idempotency_key", "operation", "arguments"}
MAX_ENVELOPE = 64 * 1024


class MissionBlocked(ValueError):
    pass


@dataclass(frozen=True)
class Task:
    mission_id: str
    task_id: str
    idempotency_key: str
    operation: str
    workspace: str
    arguments_json: str
    request_hash: str

    @property
    def arguments(self):
        return relay.strict_json(self.arguments_json)


def task_from(payload, workspace):
    if not isinstance(payload, dict) or set(payload) != TASK_KEYS:
        raise MissionBlocked("task_schema")
    for name in ("mission_id", "task_id", "idempotency_key"):
        if not isinstance(payload[name], str) or not IDENTIFIER.fullmatch(payload[name]):
            raise MissionBlocked("task_identity")
    if (not isinstance(payload["operation"], str) or payload["operation"] not in OPERATIONS
            or not isinstance(payload["arguments"], dict)):
        raise MissionBlocked("operation_not_allowed")
    try:
        canonical = relay.json_canonical(payload)
        args = relay.json_canonical(payload["arguments"])
        if len(canonical.encode()) > MAX_ENVELOPE:
            raise MissionBlocked("task_size")
        if set(relay.strict_json(canonical)) != TASK_KEYS:
            raise MissionBlocked("task_schema")
    except (TypeError, UnicodeError, RecursionError) as exc:
        raise MissionBlocked("task_schema") from exc
    return Task(payload["mission_id"], payload["task_id"], payload["idempotency_key"],
                payload["operation"], workspace, args, digest(canonical))


class LocalMissionController(Controller):
    database_name = "p2-missions.sqlite3"

    def __init__(self, folder, workspace, admit, invoke):
        if not isinstance(workspace, str) or not re.fullmatch(r"[0-9a-f]{64}", workspace):
            raise MissionBlocked("workspace_binding_invalid")
        if not callable(admit) or not callable(invoke):
            raise MissionBlocked("local_admission_adapter_required")
        super().__init__(folder, None, {})
        self.workspace, self.admit_task, self.invoke_task = workspace, admit, invoke

    def __enter__(self):
        if any(os.path.lexists(self.folder / name) for name in ("state.json", Controller.database_name)):
            raise MissionBlocked("public_lane_forbidden")
        super().__enter__()
        try:
            if self.db.execute("SELECT 1 FROM tasks LIMIT 1").fetchone():
                raise MissionBlocked("public_lane_forbidden")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS p2_missions(
                  mission_id TEXT NOT NULL, task_id TEXT NOT NULL, idem TEXT UNIQUE NOT NULL,
                  workspace TEXT NOT NULL, request TEXT NOT NULL, request_hash TEXT NOT NULL,
                  phase TEXT NOT NULL, attempt_id TEXT, epoch INTEGER NOT NULL DEFAULT 0,
                  lease TEXT, approval_sha256 TEXT, evidence TEXT, evidence_sha256 TEXT,
                  error_code TEXT, PRIMARY KEY(mission_id, task_id)
                );
                UPDATE p2_missions SET phase='UNKNOWN_OUTCOME',error_code='interrupted'
                  WHERE phase='EXECUTING';
                UPDATE p2_missions SET phase='QUEUED',lease=NULL WHERE phase='CLAIMED';
            """)
        except BaseException:
            super().__exit__(None, None, None)
            raise
        return self

    def row(self, mission, task):
        item = self.db.execute("SELECT * FROM p2_missions WHERE mission_id=? AND task_id=?",
                               (mission, task)).fetchone()
        if item is None:
            raise MissionBlocked("unknown_task")
        if item["workspace"] != self.workspace:
            raise MissionBlocked("workspace_mismatch")
        return item

    def authorize(self, task):
        reference = self.admit_task(task)
        if not isinstance(reference, str) or not IDENTIFIER.fullmatch(reference):
            raise MissionBlocked("unverified_admission")
        return digest(reference)

    def enqueue(self, payload):
        task = task_from(payload, self.workspace)
        existing = self.db.execute(
            "SELECT * FROM p2_missions WHERE idem=? OR (mission_id=? AND task_id=?)",
            (task.idempotency_key, task.mission_id, task.task_id),
        ).fetchall()
        if existing:
            if len(existing) != 1 or (existing[0]["workspace"], existing[0]["request_hash"]) != (
                    task.workspace, task.request_hash):
                raise MissionBlocked("idempotency_conflict")
            return existing[0]["phase"]
        self.authorize(task)
        with self.db:
            self.db.execute("""
                INSERT INTO p2_missions(mission_id,task_id,idem,workspace,request,request_hash,phase)
                VALUES (?,?,?,?,?,?,'QUEUED')
            """, (task.mission_id, task.task_id, task.idempotency_key, task.workspace,
                  relay.json_canonical(payload), task.request_hash))
        return "QUEUED"

    def transition(self, mission, task, phase, error=None):
        with self.db:
            self.db.execute("UPDATE p2_missions SET phase=?,error_code=? WHERE mission_id=? AND task_id=?",
                            (phase, error, mission, task))
        return phase

    def cancel(self, mission, task):
        row = self.row(mission, task)
        if row["phase"] == "QUEUED":
            return self.transition(mission, task, "CANCELLED")
        return row["phase"]

    def status(self, mission, task):
        row = self.row(mission, task)
        keys = ("mission_id", "task_id", "attempt_id", "epoch", "phase", "evidence_sha256", "error_code")
        return {key: row[key] for key in keys}

    def run(self, mission, task_id):
        row = self.row(mission, task_id)
        if row["phase"] != "QUEUED":
            return row["phase"]
        if stopped(self.folder):
            return "STOPPED"
        task = task_from(relay.strict_json(row["request"]), self.workspace)
        if (task.mission_id, task.task_id, task.idempotency_key, task.request_hash) != (
                mission, task_id, row["idem"], row["request_hash"]):
            return self.transition(mission, task_id, "BLOCKED", "task_integrity")
        try:
            approval = self.authorize(task)
        except (MissionBlocked, PermissionError):
            return self.transition(mission, task_id, "BLOCKED", "admission_denied")
        with self.db:
            self.db.execute("""
                UPDATE p2_missions SET phase='CLAIMED',attempt_id=?,epoch=epoch+1,lease=?,approval_sha256=?
                WHERE mission_id=? AND task_id=?
            """, (uuid.uuid4().hex, self.lease, approval, mission, task_id))
        try:
            if stopped(self.folder):
                self.transition(mission, task_id, "QUEUED")
                return "STOPPED"
            if self.authorize(task) != approval:
                raise MissionBlocked("admission_changed")
        except (MissionBlocked, PermissionError):
            return self.transition(mission, task_id, "BLOCKED", "admission_denied")
        self.transition(mission, task_id, "EXECUTING")
        if stopped(self.folder):
            self.transition(mission, task_id, "QUEUED")
            return "STOPPED"
        try:
            result = self.invoke_task(task.operation, task.arguments)
            if not isinstance(result, dict):
                raise MissionBlocked("result_schema")
            evidence = relay.json_canonical(result)
            if len(evidence.encode()) > MAX_ENVELOPE:
                raise MissionBlocked("result_size")
            if self.authorize(task) != approval:
                raise MissionBlocked("admission_changed")
        except (OSError, ValueError, TypeError, RecursionError):
            return self.transition(mission, task_id, "UNKNOWN_OUTCOME", "unverified_execution")
        failed_test = task.operation == "test.run" and result.get("returncode") != 0
        phase = "FAILED" if failed_test or result.get("audit") == "FAIL" else "COMPLETED"
        with self.db:
            updated = self.db.execute("""
                UPDATE p2_missions SET phase=?,evidence=?,evidence_sha256=?
                WHERE mission_id=? AND task_id=? AND phase='EXECUTING' AND lease=?
            """, (phase, evidence, digest(evidence), mission, task_id, self.lease))
            if updated.rowcount != 1:
                raise MissionBlocked("execution_fence_lost")
        return phase
