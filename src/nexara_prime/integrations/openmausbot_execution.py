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
from urllib.parse import urlsplit


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
                        " status TEXT NOT NULL, message_id TEXT, report TEXT, since_ms INTEGER)")
        if "since_ms" not in {r[1] for r in self.db.execute("PRAGMA table_info(missions)")}:
            try:
                self.db.execute("ALTER TABLE missions ADD COLUMN since_ms INTEGER")
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    raise
        # Race-safe: two separate NEXARA missions may never treat the same
        # OpenMausBot conversation as their own execution receipt.
        self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS missions_omb_thread "
                        "ON missions(bot_id, thread_id)")

    def get(self, mission_id: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT id,bot_id,thread_id,objective,send_id,status,message_id,report,"
                              "since_ms FROM missions WHERE id=?", (mission_id,)).fetchone()
        if row is None:
            return None
        return dict(zip(("id", "bot_id", "thread_id", "objective", "send_id", "status",
                         "message_id", "report", "since_ms"), row))

    def create(self, mission_id: str, bot_id: str, thread_id: str, objective: str) -> dict[str, Any]:
        if not all(isinstance(x, str) and x.strip() for x in (mission_id, bot_id, thread_id, objective)):
            raise ProofError("invalid_mission")
        if len(objective) > 12_000 or len(mission_id) > 128:
            raise ProofError("mission_size_invalid")
        send_id = "nexa-" + hashlib.sha256(mission_id.encode()).hexdigest()[:48]
        # CLI wait observes a conversation's job, not a particular message:
        # bind one NEXARA mission to each dedicated OpenMausBot thread.
        self.db.execute("INSERT OR IGNORE INTO missions "
                        "(id,bot_id,thread_id,objective,send_id,status) VALUES (?,?,?,?,?,'QUEUED')",
                        (mission_id, bot_id, thread_id, objective, send_id))
        row = self.get(mission_id)
        if row is None:
            raise ProofError("thread_already_bound_to_mission")
        if (row["bot_id"], row["thread_id"], row["objective"]) != (bot_id, thread_id, objective):
            raise ProofError("mission_id_conflict")
        return row

    def transition(self, mission_id: str, status: str, *, message_id: str | None = None,
                   report: dict[str, Any] | None = None, since_ms: int | None = None) -> dict[str, Any]:
        if status not in {"QUEUED", "SENT", "AWAITING_CONNECTIVITY", "WAITING_FOR_DEVICE", "RUNNING",
                          "NEEDS_INPUT", "REPORTED", "EXECUTION_FAILED"}:
            raise ProofError("invalid_status")
        if since_ms is not None and (type(since_ms) is not int or since_ms < 0):
            raise ProofError("invalid_job_anchor")
        # An in-flight wait can finish after a different worker has already
        # persisted the final receipt. Never turn REPORTED back into RUNNING.
        self.db.execute("UPDATE missions SET status=?,message_id=COALESCE(?,message_id),"
                        "report=COALESCE(?,report),since_ms=COALESCE(?,since_ms) WHERE id=? "
                        "AND status NOT IN ('REPORTED','EXECUTION_FAILED')",
                        (status, message_id, json.dumps(report, ensure_ascii=False) if report is not None else None,
                         since_ms, mission_id))
        result = self.get(mission_id)
        if result is None:
            raise ProofError("mission_not_found")
        return result


class OMBCLI:
    """Explicit binary + server; no shell interpolation, no auto-start or model call."""

    def __init__(self, *, executable: str = "openmausbot", url: str = "http://127.0.0.1:8799",
                 token_file: str | None = None, runner: Callable[..., Any] = subprocess.run):
        try:
            origin = urlsplit(url)
            valid = (origin.scheme == "https" and bool(origin.hostname)) or (
                origin.scheme == "http" and origin.hostname in {"localhost", "127.0.0.1"}
                and origin.port is not None)
            valid = valid and origin.username is None and origin.password is None
            valid = valid and not origin.path.strip("/") and not origin.query and not origin.fragment
            if origin.port is not None and not (1 <= origin.port <= 65535):
                valid = False
        except ValueError:
            valid = False
        if not valid:
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
        if record["status"] in {"SENT", "WAITING_FOR_DEVICE", "RUNNING", "NEEDS_INPUT", "REPORTED", "EXECUTION_FAILED"}:
            return record
        # The official run --wait none records the server's clock BEFORE
        # sending. wait --since then binds a receipt to this execution epoch.
        try:
            code, result = self.cli.call("run", "--bot", bot_id, "-", "--task", thread_id,
                                         "--send-id", record["send_id"], "--wait", "none",
                                         message=record["objective"])
        except ProofError as exc:
            if str(exc) == "cli_unavailable_or_timeout":
                return self.ledger.transition(mission_id, "AWAITING_CONNECTIVITY")
            raise
        if code != 0 or result.get("ok") is not True:
            if code in {4, 5}:
                return self.ledger.transition(mission_id, "AWAITING_CONNECTIVITY")
            raise CLIResponseError(code, result)
        if (result.get("threadId") != thread_id or not result.get("messageId")
                or result.get("sendId") != record["send_id"]):
            raise ProofError("send_ack_mismatch")
        if result.get("queued") is True or result.get("steered") is True:
            # A busy conversation may complete its previous job first.
            return self.ledger.transition(mission_id, "NEEDS_INPUT", message_id=str(result["messageId"]),
                                          report={"reason": "nonexclusive_thread_send"})
        since, at = result.get("since"), result.get("at")
        if type(since) is not int or type(at) is not int or since < 0 or at < since:
            # After an ambiguous send timeout, a duplicate ack may be older
            # than the new clock. Never certify that job with the new anchor.
            return self.ledger.transition(mission_id, "NEEDS_INPUT", message_id=str(result["messageId"]),
                                          report={"reason": "ambiguous_job_anchor", "at": at, "since": since})
        return self.ledger.transition(mission_id, "SENT", message_id=str(result["messageId"]), since_ms=since)

    def submit_proposal(self, proposal: dict[str, Any], bot_id: str,
                        thread_id: str) -> dict[str, Any]:
        """One-call bridge from NEXARA cognitive goal proposal to OMB work.

        The caller supplies an already-provisioned laboratory thread. HYPOTHESIS
        means a free research idea, not a verified claim or production right.
        """
        if (proposal.get("status") not in {"HYPOTHESIS", "EVIDENCE_BACKED"}
            or not isinstance(proposal.get("proposal_id"), str)
            or not isinstance(proposal.get("objective"), str)):
            raise ProofError("invalid_cognitive_proposal")
        return self.submit(proposal["proposal_id"], bot_id, thread_id, proposal["objective"])

    def reconcile(self, mission_id: str) -> dict[str, Any]:
        rec = self.ledger.get(mission_id)
        if rec is None:
            raise ProofError("mission_not_found")
        if rec["status"] in {"QUEUED", "AWAITING_CONNECTIVITY"}:
            return self.submit(rec["id"], rec["bot_id"], rec["thread_id"], rec["objective"])
        if rec["status"] in {"REPORTED", "EXECUTION_FAILED"}:
            return rec
        if rec["since_ms"] is None:
            # Legacy AEP-01 jobs have no durable execution epoch.
            return self.ledger.transition(mission_id, "NEEDS_INPUT", report={"reason": "missing_job_anchor"})
        try:
            code, result = self.cli.call("wait", "--bot", rec["bot_id"],
                                         "--task", rec["thread_id"], "--since", str(rec["since_ms"]),
                                         "--timeout", "60s", "--strict")
        except ProofError as exc:
            if str(exc) == "cli_unavailable_or_timeout":
                return self.ledger.transition(mission_id, "WAITING_FOR_DEVICE")
            raise
        state = result.get("state")
        if code == 5:
            return self.ledger.transition(mission_id, "WAITING_FOR_DEVICE")
        if code == 4 or state in {"timed-out", "running"}:
            return self.ledger.transition(mission_id, "RUNNING")
        if code == 3 or state == "needs-input":
            return self.ledger.transition(mission_id, "NEEDS_INPUT", report=result)
        job = result.get("job")
        nodes = job.get("nodes") if isinstance(job, dict) else None
        if (result.get("taskId") != rec["thread_id"] or not isinstance(job, dict)
            or job.get("threadId") != rec["thread_id"]
            or type(job.get("since")) is not int or job["since"] < rec["since_ms"]
            or not isinstance(nodes, list) or not nodes or not all(isinstance(n, dict) for n in nodes)):
            return self.ledger.transition(mission_id, "EXECUTION_FAILED",
                                          report={"reason": "unbound_job_receipt", "raw": result})
        counts = job.get("counts") or {}
        failed_counts = (not isinstance(counts, dict) or any(
            type(counts.get(k, 0)) is not int or counts.get(k, 0) > 0 for k in ("failed", "cancelled")))
        all_complete = all(n.get("status") == "completed" for n in nodes)
        if code == 0 and result.get("ok") is True and state == "completed" and all_complete and not failed_counts:
            return self.ledger.transition(mission_id, "REPORTED", report=result)
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
