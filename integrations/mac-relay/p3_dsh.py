"""Bounded DSH task executor for the P3 `dsh.task.run` operation (B1, isolated).

The executor never decides authorization: the P3 admission chain does that first and
passes only an already-admitted task here. This module owns four things only:

  * a hard ceiling of 20 seconds on any task,
  * an allowlist of task kinds,
  * refusal to run unless the injected adapter can name a zero-incremental-cost route,
  * a result digest bound into the signed receipt.
"""
from __future__ import annotations

import hashlib
import subprocess

import relay

MAX_TASK_SECONDS = 20
TASK_KINDS = frozenset({"readonly-inspect"})
DSH_ARGUMENTS = frozenset({"task_kind", "instruction", "instruction_sha256"})


class DshError(Exception):
    pass


def task_arguments(task):
    """Task.arguments is the canonical JSON string in some revisions and a dict in others."""
    value = task.arguments
    return relay.strict_json(value) if isinstance(value, str) else value


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def result_digest(exit_code: int, stdout_sha: str, stderr_sha: str) -> str:
    """Binds the exit code to both stream digests so no field can be edited alone."""
    return _sha(("dsh1|%d|%s|%s" % (exit_code, stdout_sha, stderr_sha)).encode())


def run_task(*, workspace, instruction, timeout, adapter):
    """Run one bounded task through the injected adapter.

    adapter(instruction, timeout, workspace) -> {"exit_code", "stdout", "stderr",
    "zero_cost_route"}. An empty zero_cost_route is refused, so an unproven paid
    route can never be exercised through this policy.
    """
    if type(timeout) is not int or not 1 <= timeout <= MAX_TASK_SECONDS:
        raise DshError("timeout_out_of_bounds")
    if not isinstance(instruction, str) or not instruction:
        raise DshError("instruction_missing")
    if adapter is None:
        raise DshError("model_cost_unverified")
    try:
        outcome = adapter(instruction, timeout, str(workspace))
    except subprocess.TimeoutExpired as exc:
        raise DshError("task_timeout") from exc
    except OSError as exc:
        raise DshError("adapter_failed") from exc
    if not isinstance(outcome, dict) or set(outcome) != {"exit_code", "stdout", "stderr", "zero_cost_route"}:
        raise DshError("adapter_contract")
    route = outcome["zero_cost_route"]
    if not isinstance(route, str) or not route:
        raise DshError("model_cost_unverified")
    if type(outcome["exit_code"]) is not int:
        raise DshError("adapter_contract")
    if not isinstance(outcome["stdout"], bytes) or not isinstance(outcome["stderr"], bytes):
        raise DshError("adapter_contract")
    return {
        "exit_code": outcome["exit_code"],
        "stdout_sha256": _sha(outcome["stdout"]),
        "stderr_sha256": _sha(outcome["stderr"]),
        "stdout_bytes": len(outcome["stdout"]),
        "result_sha256": result_digest(outcome["exit_code"], _sha(outcome["stdout"]), _sha(outcome["stderr"])),
        "zero_cost_route": route,
    }


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
        "budget_microusd": contract["budget_microusd"],
        "zero_cost_route": outcome["zero_cost_route"],
        "exit_code": outcome["exit_code"],
        "stdout_sha256": outcome["stdout_sha256"],
        "stderr_sha256": outcome["stderr_sha256"],
        "stdout_bytes": outcome["stdout_bytes"],
        "result_sha256": result_digest(outcome["exit_code"], outcome["stdout_sha256"],
                                     outcome["stderr_sha256"]),
        "dispatched_at": times[0],
        "finished_at": times[1],
        "model_calls": 0,
    }


def verify_dsh_evidence(evidence, approved, task, state):
    if not isinstance(evidence, dict):
        raise DshError("dsh_evidence_integrity")
    times = (evidence.get("dispatched_at"), evidence.get("finished_at"))
    outcome = {key: evidence.get(key) for key in
               ("exit_code", "stdout_sha256", "stderr_sha256", "stdout_bytes",
                "result_sha256", "zero_cost_route")}
    expected = dsh_evidence(approved, task, state, outcome, times)
    if expected != evidence:
        raise DshError("dsh_evidence_integrity")
    return expected
