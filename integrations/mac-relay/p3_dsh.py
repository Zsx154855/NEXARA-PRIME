"""Bounded DSH task executor for the P3 `dsh.task.run` operation (B1, isolated).

The executor never decides authorization: the P3 admission chain does that first and
passes only an already-admitted task here. This module owns four things only:

  * a hard ceiling of 20 seconds on any task,
  * an allowlist of task kinds,
  * refusal to run unless the injected adapter can name a zero-incremental-cost route,
  * a result digest bound into the signed receipt.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import signal
import subprocess
import time

import relay
from p3_dsh_route import RouteError, verify_route

MAX_TASK_SECONDS = 20
DEADLINE_SLACK_SECONDS = 1.0
TASK_KINDS = frozenset({"readonly-inspect"})
DSH_ARGUMENTS = frozenset({"task_kind", "instruction", "instruction_sha256", "route"})


class DshError(Exception):
    pass


def task_arguments(task):
    """Task.arguments is the canonical JSON string in some revisions and a dict in others."""
    value = task.arguments
    return relay.strict_json(value) if isinstance(value, str) else value


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def result_digest(exit_code: int, stdout_sha: str, stderr_sha: str, metering=None) -> str:
    """Binds exit code, both stream digests and the metering record into one hash."""
    metering_sha = _sha(relay.json_canonical(metering).encode()) if metering is not None else ""
    return _sha(("dsh2|%d|%s|%s|%s" % (exit_code, stdout_sha, stderr_sha, metering_sha)).encode())


def run_task(*, workspace, instruction, timeout, route, adapter, prober=None, environ=None):
    """Verify the route first, then run one bounded task through the injected adapter.

    adapter(instruction, timeout, workspace) -> {"exit_code", "stdout", "stderr", "metering"}
    metering = {"model_calls": int | "unknown", "source": str}
    """
    if type(timeout) is not int or not 1 <= timeout <= MAX_TASK_SECONDS:
        raise DshError("timeout_out_of_bounds")
    if not isinstance(instruction, str) or not instruction:
        raise DshError("instruction_missing")
    if adapter is None:
        raise DshError("model_cost_unverified")
    try:
        proof = verify_route(route, prober=prober, environ=environ)
    except RouteError as exc:
        raise DshError(str(exc)) from exc
    started = time.monotonic()
    try:
        outcome = adapter(instruction, timeout, str(workspace))
    except subprocess.TimeoutExpired as exc:
        raise DshError("task_timeout") from exc
    except OSError as exc:
        raise DshError("adapter_failed") from exc
    elapsed = time.monotonic() - started
    if elapsed > timeout + DEADLINE_SLACK_SECONDS:
        raise DshError("deadline_exceeded")
    if not isinstance(outcome, dict) or set(outcome) != {"exit_code", "stdout", "stderr", "metering"}:
        raise DshError("adapter_contract")
    if type(outcome["exit_code"]) is not int:
        raise DshError("adapter_contract")
    if not isinstance(outcome["stdout"], bytes) or not isinstance(outcome["stderr"], bytes):
        raise DshError("adapter_contract")
    metering = outcome["metering"]
    if (not isinstance(metering, dict) or set(metering) != {"model_calls", "source"}
            or not isinstance(metering["source"], str) or not metering["source"]):
        raise DshError("metering_unverified")
    calls = metering["model_calls"]
    if not (calls == "unknown" or (type(calls) is int and calls >= 0)):
        raise DshError("metering_unverified")
    return {
        "exit_code": outcome["exit_code"],
        "stdout_sha256": _sha(outcome["stdout"]),
        "stderr_sha256": _sha(outcome["stderr"]),
        "stdout_bytes": len(outcome["stdout"]),
        "result_sha256": result_digest(outcome["exit_code"], _sha(outcome["stdout"]), _sha(outcome["stderr"]),
                                       {"model_calls": calls, "source": metering["source"]}),
        "route": proof,
        "metering": {"model_calls": calls, "source": metering["source"]},
        "elapsed_seconds": round(elapsed, 3),
    }


class ProcessAdapter:
    """Real subprocess adapter: own process group, hard deadline, verified termination."""

    def __init__(self, argv, metering_source="dsh-process"):
        self.argv = list(argv)
        self.metering_source = metering_source

    def __call__(self, instruction, timeout, workspace):
        process = subprocess.Popen(self.argv + [instruction], cwd=workspace, env={},
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        try:
            out, err = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.terminate(process)
            raise
        return {"exit_code": process.returncode, "stdout": out, "stderr": err,
                "metering": {"model_calls": "unknown", "source": self.metering_source}}

    @staticmethod
    def terminate(process):
        """SIGKILL the whole group, reap it, and prove the child is gone."""
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.communicate(timeout=5)
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        try:
            os.kill(process.pid, 0)
        except ProcessLookupError:
            return True
        raise DshError("child_not_reaped")


def dsh_evidence(approved, task, state, outcome, times):
    args = task_arguments(task)
    contract = approved["contract"]
    return {
        "operation": "dsh.task.run",
        "attempt_id": state["attempt_id"],
        "execution_epoch": state["epoch"],
        "mission_id": task.mission_id,
        "task_id": task.task_id,
        "task_kind": args["task_kind"],
        "instruction_sha256": args["instruction_sha256"],
        "contract_sha256": _sha(relay.json_canonical(contract).encode()),
        "grant_sha256": approved["signed_grant_sha256"],
        "workspace": contract["workspace"],
        "head": contract["head"],
        "max_seconds": contract["max_seconds"],
        "route": outcome["route"],
        "metering": outcome["metering"],
        "elapsed_seconds": outcome["elapsed_seconds"],
        "budget_microusd": contract["budget_microusd"],
        "exit_code": outcome["exit_code"],
        "stdout_sha256": outcome["stdout_sha256"],
        "stderr_sha256": outcome["stderr_sha256"],
        "stdout_bytes": outcome["stdout_bytes"],
        "result_sha256": result_digest(outcome["exit_code"], outcome["stdout_sha256"],
                                     outcome["stderr_sha256"], outcome["metering"]),
        "dispatched_at": times[0],
        "finished_at": times[1],
    }


def verify_dsh_evidence(evidence, approved, task, state):
    if not isinstance(evidence, dict):
        raise DshError("dsh_evidence_integrity")
    times = (evidence.get("dispatched_at"), evidence.get("finished_at"))
    outcome = {key: evidence.get(key) for key in
               ("exit_code", "stdout_sha256", "stderr_sha256", "stdout_bytes",
                "result_sha256", "route", "metering", "elapsed_seconds")}
    expected = dsh_evidence(approved, task, state, outcome, times)
    if expected != evidence:
        raise DshError("dsh_evidence_integrity")
    return expected
