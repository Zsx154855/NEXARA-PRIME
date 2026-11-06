"""NAEOS: bounded two-task subprocess execution with SQLite checkpoints.

This adapter is not a daemon and is not an OS sandbox. Its caller must supply
a disposable, authorized workspace with approved local Python scripts.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nexara_prime.models import new_id
from .persistent_runtime import Checkpoint, StateManager


@dataclass(frozen=True)
class LocalWorkerTask:
    task_id: str
    script_path: str


class ContinuousLocalWorker:
    """Sequential task A→B runner; no fabricated worker callbacks."""

    def __init__(
        self, *,
        state: StateManager,
        evidence_store: Any,
        workdir: Path,
        mission_id: str,
        project_id: str,
        tasks: tuple[LocalWorkerTask, ...],
        timeout_s: int = 60,
        max_log_bytes: int = 262144,
    ) -> None:
        self.state = state
        self.evidence = evidence_store
        self.workdir = Path(workdir).resolve(strict=True)
        self.mission_id = mission_id
        self.project_id = project_id
        self.tasks = tasks
        self.timeout_s = timeout_s
        self.max_log_bytes = max_log_bytes
        if len(tasks) != 2 or len({t.task_id for t in tasks}) != 2:
            raise ValueError("two_distinct_tasks_required")
        if not 1 <= timeout_s <= 900:
            raise ValueError("invalid_timeout")
        for task in tasks:
            path = (self.workdir / task.script_path).resolve(strict=True)
            if (
                not path.is_relative_to(self.workdir)
                or path.suffix != ".py"
                or not path.is_file()
            ):
                raise ValueError("worker_script_not_in_authorized_workspace")

    @contextmanager
    def _exclusive(self):
        lock = self.workdir / ".naeos-worker.lock"
        with lock.open("a+b") as fh:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("worker_lease_busy") from exc
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def _load_or_create(self) -> Checkpoint:
        cp = self.state.load_checkpoint(self.mission_id, self.project_id)
        planned = [t.task_id for t in self.tasks]
        if cp:
            if cp.data.get("planned_tasks") != planned:
                raise ValueError("checkpoint_task_contract_mismatch")
            return cp
        cp = Checkpoint(
            checkpoint_id=new_id("cp"), mission_id=self.mission_id,
            project_id=self.project_id, run_id=new_id("run"),
            trace_id=new_id("trace"), state="created", step_index=0,
            pending_actions=planned.copy(), data={"planned_tasks": planned, "receipts": {}},
        )
        self.state.save_checkpoint(cp)
        return cp

    def run(self, *, max_steps: int = 2) -> dict[str, Any]:
        if max_steps not in (1, 2):
            raise ValueError("max_steps_must_be_one_or_two")
        with self._exclusive():
            cp = self._load_or_create()
            if not self._prior_receipts_valid(cp):
                cp.state = "blocked"
                cp.data["error"] = "prior_receipt_unverified"
                self.state.save_checkpoint(cp)
                return self._report(cp)
            if cp.state in {"failed", "blocked", "completed"}:
                return self._report(cp)
            executed = 0
            while cp.step_index < len(self.tasks) and executed < max_steps:
                task = self.tasks[cp.step_index]
                if self.state.is_duplicate(
                    self.project_id, self.mission_id, "naeos_task", task.task_id
                ):
                    cp.state = "blocked"
                    cp.data["error"] = "idempotency_replay_requires_reconciliation"
                    self.state.save_checkpoint(cp)
                    break
                cp.state = "running"
                self.state.save_checkpoint(cp)
                cmd = [sys.executable, str((self.workdir / task.script_path).resolve())]
                env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "HOME") if k in os.environ}
                env["PYTHONNOUSERSITE"] = "1"
                try:
                    proc = subprocess.run(
                        cmd, cwd=self.workdir, env=env, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, timeout=self.timeout_s, check=False,
                    )
                except (subprocess.TimeoutExpired, OSError) as exc:
                    cp.state = "blocked"
                    cp.data["error"] = f"worker_process_error:{type(exc).__name__}"
                    self.state.save_checkpoint(cp)
                    break
                log = proc.stdout or b""
                if len(log) > self.max_log_bytes:
                    cp.state = "blocked"
                    cp.data["error"] = "worker_log_limit_exceeded"
                    self.state.save_checkpoint(cp)
                    break
                invocation_id = new_id("tool")
                receipt = {
                    "mission_id": self.mission_id,
                    "project_id": self.project_id,
                    "run_id": cp.run_id,
                    "task_id": task.task_id,
                    "attempt_number": 1,
                    "tool_invocation_id": invocation_id,
                    "argv": cmd,
                    "exit_code": proc.returncode,
                    "stdout_sha256": hashlib.sha256(log).hexdigest(),
                    "stdout_b64": base64.b64encode(log).decode("ascii"),
                }
                if self.evidence is None:
                    cp.state = "blocked"
                    cp.data["error"] = "worker_evidence_store_missing"
                    self.state.save_checkpoint(cp)
                    break
                try:
                    artifact = self.evidence.add(
                        self.mission_id, "naeos_worker_receipt", "real worker process",
                        json.dumps(receipt, sort_keys=True), cp.trace_id,
                        task_id=task.task_id, tool_invocation_id=invocation_id,
                        actor="naeos-local-controller", source="host-subprocess",
                        idempotency_key=f"naeos:{self.mission_id}:{cp.run_id}:{task.task_id}",
                    )
                    if (
                        self.evidence.verify(artifact.evidence_id) is not True
                        or self.evidence.is_preverified_and_integrity_bound(
                            artifact.evidence_id
                        ) is not True
                    ):
                        raise ValueError("worker_evidence_invalid")
                except (OSError, ValueError, RuntimeError, KeyError, AttributeError):
                    cp.state = "blocked"
                    cp.data["error"] = "worker_evidence_unverified"
                    self.state.save_checkpoint(cp)
                    break
                if proc.returncode != 0:
                    cp.state = "failed"
                    cp.data["error"] = f"worker_process_exit:{proc.returncode}"
                    cp.data["failed_receipt"] = artifact.evidence_id
                    self.state.save_checkpoint(cp)
                    break
                if not self.state.record_effect(
                    self.project_id, self.mission_id, "naeos_task",
                    task.task_id, receipt["stdout_sha256"],
                ):
                    cp.state = "blocked"
                    cp.data["error"] = "worker_duplicate_effect"
                    self.state.save_checkpoint(cp)
                    break
                cp.data["receipts"][task.task_id] = artifact.evidence_id
                cp.completed_actions.append(task.task_id)
                cp.pending_actions.remove(task.task_id)
                cp.step_index += 1
                cp.state = "completed" if cp.step_index == len(self.tasks) else "paused"
                self.state.save_checkpoint(cp)
                executed += 1
            return self._report(cp)

    def _prior_receipts_valid(self, cp: Checkpoint) -> bool:
        for task_id, evidence_id in cp.data.get("receipts", {}).items():
            if self.evidence is None:
                return False
            try:
                if self.evidence.is_preverified_and_integrity_bound(evidence_id) is not True:
                    return False
                artifact = self.evidence.get_by_id(evidence_id)
                data = json.loads(artifact.content)
                raw = base64.b64decode(data["stdout_b64"], validate=True)
                if (
                    artifact.mission_id != self.mission_id
                    or artifact.task_id != task_id
                    or data["task_id"] != task_id
                    or data["mission_id"] != self.mission_id
                    or data["run_id"] != cp.run_id
                    or data["exit_code"] != 0
                    or hashlib.sha256(raw).hexdigest() != data["stdout_sha256"]
                ):
                    return False
            except (KeyError, ValueError, TypeError, AttributeError, RuntimeError):
                return False
        return True

    def _report(self, cp: Checkpoint) -> dict[str, Any]:
        return {
            "mission_id": cp.mission_id, "run_id": cp.run_id,
            "status": cp.state, "completed": list(cp.completed_actions),
            "pending": list(cp.pending_actions),
            "receipts": dict(cp.data.get("receipts", {})),
            "error": cp.data.get("error", ""),
        }
