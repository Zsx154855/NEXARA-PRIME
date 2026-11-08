"""NEXARA -> OpenMausBot execution probe, without reimplementing Agent scheduling.

Driver is the published OpenMausBot headless CLI (0.1.148). Work is sent to
an *existing, pinned* bot task. The deterministic send-id survives crashes;
OpenMausBot deduplicates sends. A job result is not a verification receipt.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
from typing import Any, Callable


class ProofError(RuntimeError):
    pass


class CLIResponseError(ProofError):
    def __init__(self, status: int, result: dict[str, Any]):
        self.status, self.result = status, result
        super().__init__(f"openmausbot_exit_{status}")


class TaskLedger:
    """SQLite holds the top-level mission; OMB holds the Agent subtree."""

    def __init__(self, path: Path):
        self.db = sqlite3.connect(str(path), isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("CREATE TABLE IF NOT EXISTS missions (id TEXT PRIMARY KEY,"
                        " bot_id TEXT NOT NULL, thread_id TEXT NOT NULL,"
                        " objective TEXT NOT NULL, send_id TEXT NOT NULL UNIQUE,"
                        " status TEXT NOT NULL, message_id TEXT, report TEXT)")

    def get(self, mission_id: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT id,bot_id,thread_id,objective,send_id,status,message_id,report "
                              "FROM missions WHERE id=?", (mission_id,)).fetchone()
        if row is None:
            return None
        return dict(zip(("id", "bot_id", "thread_id", "objective", "send_id", "status",
                         "message_id", "report"), row))

    def create(self, mission_id: str, bot_id: str, thread_id: str, objective: str) -> dict[str, Any]:
        if not all(isinstance(x, str) and x.strip() for x in (mission_id, bot_id, thread_id, objective)):
            raise ProofError("invalid_mission")
        if len(objective) > 12_000 or len(mission_id) > 128:
            raise ProofError("mission_size_invalid")
        send_id = "nexa-" + hashlib.sha256(mission_id.encode()).hexdigest()[:48]
        # CLI wait observes a conversation's job, not a particular message:
        # bind one NEXARA mission to each dedicated OpenMausBot thread.
        existing = self.db.execute("SELECT id FROM missions WHERE bot_id=? AND thread_id=? AND id<>?",
                                   (bot_id, thread_id, mission_id)).fetchone()
        if existing:
            raise ProofError("thread_already_bound_to_mission")
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO missions VALUES (?,?,?,?,?,'QUEUED',NULL,NULL)",
                            (mission_id, bot_id, thread_id, objective, send_id))
        row = self.get(mission_id)
        if (row["bot_id"], row["thread_id"], row["objective"]) != (bot_id, thread_id, objective):
            raise ProofError("mission_id_conflict")
        return row

    def transition(self, mission_id: str, status: str, *, message_id: str | None = None,
                   report: dict[str, Any] | None = None) -> dict[str, Any]:
        if status not in {"QUEUED", "SENT", "AWAITING_CONNECTIVITY", "RUNNING",
                          "NEEDS_INPUT", "REPORTED", "EXECUTION_FAILED"}:
            raise ProofError("invalid_status")
        with self.db:
            self.db.execute("UPDATE missions SET status=?,message_id=COALESCE(?,message_id),"
                            "report=COALESCE(?,report) WHERE id=?",
                            (status, message_id, json.dumps(report, ensure_ascii=False) if report is not None else None, mission_id))
        return self.get(mission_id)


class OMBCLI:
    """Explicit binary + server; no shell interpolation, no auto-start or model call."""

    def __init__(self, *, executable: str = "openmausbot", url: str = "http://127.0.0.1:8799",
                 token_file: str | None = None, runner: Callable[..., Any] = subprocess.run):
        if not (url.startswith("http://127.0.0.1:") or url.startswith("http://localhost:")
                or url.startswith("https://")):
            raise ProofError("explicit_loopback_or_https_required")
        self.executable, self.url, self.token_file, self.runner = executable, url, token_file, runner

    def call(self, verb: str, *args: str, timeout: int = 75, message: str | None = None) -> tuple[int, dict[str, Any]]:
        argv = [self.executable, verb, *args, "--url", self.url, "--json", "--quiet"]
        if self.token_file:
            argv.extend(["--token-file", self.token_file])
        try:
            p = self.runner(argv, capture_output=True, text=True, timeout=timeout, check=False, input=message)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise ProofError("cli_unavailable_or_timeout") from exc
        try:
            result = json.loads(p.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ProofError("cli_non_json_output") from exc
        if not isinstance(result, dict):
            raise ProofError("cli_invalid_payload")
        return p.returncode, result


class ExecutionProof:
    def __init__(self, ledger: TaskLedger, cli: OMBCLI):
        self.ledger, self.cli = ledger, cli

    def submit(self, mission_id: str, bot_id: str, thread_id: str, objective: str) -> dict[str, Any]:
        record = self.ledger.create(mission_id, bot_id, thread_id, objective)
        if record["status"] in {"SENT", "RUNNING", "NEEDS_INPUT", "REPORTED", "EXECUTION_FAILED"}:
            return record
        # Stable taskId plus sendId prevent duplicate external side effects
        # on crash/retry. The task must already exist in OpenMausBot.
        code, result = self.cli.call("send", "--bot", bot_id, "-", "--task", thread_id,
                                     "--send-id", record["send_id"], message=record["objective"])
        if code != 0 or result.get("success") is not True:
            if code in {4, 5}:
                return self.ledger.transition(mission_id, "AWAITING_CONNECTIVITY")
            raise CLIResponseError(code, result)
        if result.get("taskId") != thread_id or not result.get("messageId"):
            raise ProofError("send_ack_mismatch")
        return self.ledger.transition(mission_id, "SENT", message_id=str(result["messageId"]))

    def reconcile(self, mission_id: str) -> dict[str, Any]:
        rec = self.ledger.get(mission_id)
        if rec is None:
            raise ProofError("mission_not_found")
        if rec["status"] in {"QUEUED", "AWAITING_CONNECTIVITY"}:
            return self.submit(rec["id"], rec["bot_id"], rec["thread_id"], rec["objective"])
        if rec["status"] in {"REPORTED", "EXECUTION_FAILED"}:
            return rec
        code, result = self.cli.call("wait", "--bot", rec["bot_id"],
                                     "--task", rec["thread_id"], "--timeout", "60s", "--strict")
        state = result.get("state")
        if code == 5:
            # The work was already sent. Resume waiting, never resend it.
            return self.ledger.transition(mission_id, "RUNNING")
        if code == 4 or state in {"timed-out", "running"}:
            return self.ledger.transition(mission_id, "RUNNING")
        if code == 3 or state == "needs-input":
            return self.ledger.transition(mission_id, "NEEDS_INPUT", report=result)
        nodes = (result.get("job") or {}).get("nodes") or []
        has_failed_child = any(n.get("status") in {"failed", "cancelled"} for n in nodes)
        if code == 0 and result.get("ok") is True and state == "completed" and not has_failed_child:
            return self.ledger.transition(mission_id, "REPORTED", report=result)
        # "settled" != "success", and no model-written message is test proof.
        return self.ledger.transition(mission_id, "EXECUTION_FAILED", report=result)

    def team_evidence(self, mission_id: str, minimum_unique_bots: int = 3) -> dict[str, Any]:
        rec = self.ledger.get(mission_id)
        if rec is None or rec["status"] != "REPORTED" or not rec["report"]:
            return {"delegation_observed": False, "qa_verified": False,
                    "reason": "no_successful_job_report"}
        result = json.loads(rec["report"])
        nodes = (result.get("job") or {}).get("nodes") or []
        actors = {n.get("botId") for n in nodes if n.get("status") == "completed" and n.get("botId")}
        failures = [n.get("id") for n in nodes if n.get("status") in {"failed", "cancelled"}]
        enough = len(actors) >= minimum_unique_bots and not failures
        return {"delegation_observed": enough, "qa_verified": False,
                "unique_completed_bots": len(actors), "failed_nodes": failures,
                "reason": "team_tree_reported" if enough else "insufficient_team_proof"}
