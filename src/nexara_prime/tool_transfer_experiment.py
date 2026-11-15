"""Real tool-level A->B transfer experiment (MOCK_INTEGRATION, real tool calls).

Task A executes two code_exec strategies against the real ToolRuntime, records
one verified experience per real receipt, then Task B recomputes a choice from
those experiences and executes the chosen strategy again through the same tool
runtime. No model/provider call is made; the only "learning" signal is the
tool's real exit status bound to verified execution receipts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .brain.db import BrainDB
from .brain.experience_learner import ExperienceLearner
from .brain.memory_controller import MemoryController
from .cognitive_loop import MOCK_ONLY, _mission_settings
from .runtime import NexaraRuntime

TRIALS = 3
SAFE_TOOL = "code_exec"
FAULTY_TOOL = "run_command_sandboxed"
COLD_CHOICE = FAULTY_TOOL
STRATEGIES = (SAFE_TOOL, FAULTY_TOOL)

ARGUMENTS = {
    SAFE_TOOL: {"code": "print(6 * 7)"},
    FAULTY_TOOL: {"command": ["python3", "-c", "raise SystemExit(3)"]},
}


def _invoke_strategy(
    runtime: NexaraRuntime, mission_id: str, strategy: str, attempt: str
) -> dict[str, Any]:
    """Invoke one real tool and return the persisted invocation record."""
    key = f"tool-transfer:{mission_id}:{strategy}:{attempt}"
    error = ""
    try:
        runtime.tools.invoke(
            mission_id,
            strategy,
            ARGUMENTS[strategy],
            f"trace:{mission_id}:{strategy}:{attempt}",
            idempotency_key=key,
        )
    except Exception as exc:  # the failed invocation is still persisted
        error = f"{type(exc).__name__}: {exc}"
    invocations = runtime.tools.list_invocations(mission_id)
    invocation = next(
        (row for row in invocations if row.get("idempotency_key") == key), None
    )
    if invocation is None:
        raise RuntimeError("tool_invocation_not_persisted")
    return {
        "strategy": strategy,
        "mission_id": mission_id,
        "invocation_id": str(invocation.get("invocation_id", "")),
        "evidence_id": str(invocation.get("receipt_evidence_id", "")),
        "status": str(invocation.get("status", "")),
        "success": str(invocation.get("status", "")) == "completed",
        "error": error,
        "result": invocation.get("result", {}),
    }


def run_tool_transfer(
    workdir: Path, artifact_path: Path | None = None
) -> dict[str, Any]:
    """Run Task A -> learned choice -> real Task B, plus a revoked control."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    settings = _mission_settings(workdir)
    runtime = NexaraRuntime(settings)
    brain = BrainDB(store=runtime.store)
    learner = ExperienceLearner(
        MemoryController(db=brain), evidence_store=runtime.evidence
    )
    result: dict[str, Any] = {
        "mode": MOCK_ONLY,
        "strategies": list(STRATEGIES),
        "cold_choice": COLD_CHOICE,
        "task_a": [],
        "task_b": {},
        "decision_changed": False,
        "decision_reverted": False,
        "learning_transferred_real": "NO_OUTCOME_DELTA_OBSERVED",
    }
    try:
        task_a_mission_ids: list[str] = []
        for mission_index in ("1", "2"):
            task_a = runtime.create_mission(f"Tool transfer task A{mission_index}")
            task_a_mission_ids.append(task_a.mission_id)
            for strategy in STRATEGIES:
                run = _invoke_strategy(
                    runtime, task_a.mission_id, strategy, mission_index
                )
                result["task_a"].append(run)
                if not run["evidence_id"]:
                    raise RuntimeError("tool_receipt_missing")
                learner.record_outcome(
                    task_a.mission_id,
                    "success" if run["success"] else "failure",
                    run["strategy"],
                    "exit-zero" if run["success"] else "non-zero-exit",
                    run["success"],
                    evidence_id=run["evidence_id"],
                )

        def run_arm(label: str, strategy: str) -> list[dict[str, Any]]:
            mission = runtime.create_mission(f"Tool transfer task B {label}")
            return [
                _invoke_strategy(
                    runtime, mission.mission_id, strategy, f"{label}-{trial}"
                )
                for trial in range(1, TRIALS + 1)
            ]

        cold_runs = run_arm("cold", COLD_CHOICE)
        result["task_b"]["cold"] = cold_runs

        decision = learner.recommend_action("exec")
        experienced_choice = decision.get("action") or COLD_CHOICE
        result["task_b"]["decision"] = decision
        result["task_b"]["experienced_choice"] = experienced_choice
        experienced_runs = run_arm("experienced", experienced_choice)
        result["task_b"]["experienced"] = experienced_runs
        result["decision_changed"] = experienced_choice != COLD_CHOICE

        # Retire only Task A's newly created Mission experiences.
        # Never archive unrelated active memories in this shared-store design.
        # Keep provenance in the result artifact for independent QA.
        retirement_audit: list[dict[str, Any]] = []
        for mission_id in task_a_mission_ids:
            retired = learner.retire_experiences(
                mission_id=mission_id,
                reason="tool_transfer_experiment_revoked_control",
                actor="tool_transfer_experiment",
                audit=retirement_audit.append,
            )
            if retired != len(STRATEGIES):
                raise RuntimeError("task_a_retirement_incomplete")
        result["retirement_audit"] = retirement_audit
        revoked_decision = learner.recommend_action("exec")
        revoked_choice = revoked_decision.get("action") or COLD_CHOICE
        revoked_runs = run_arm("revoked", revoked_choice)
        result["task_b"]["revoked_decision"] = revoked_decision
        result["task_b"]["revoked_choice"] = revoked_choice
        result["task_b"]["revoked"] = revoked_runs
        result["decision_reverted"] = revoked_choice == COLD_CHOICE

        def success_rate(runs: list[dict[str, Any]]) -> float:
            return round(sum(1 for run in runs if run["success"]) / len(runs), 4)

        result["trials"] = TRIALS
        result["cold_success_rate"] = success_rate(cold_runs)
        result["experienced_success_rate"] = success_rate(experienced_runs)
        result["revoked_success_rate"] = success_rate(revoked_runs)
        result["real_tool_outcome_delta"] = round(
            result["experienced_success_rate"] - result["cold_success_rate"], 4
        )
        if result["real_tool_outcome_delta"] > 0:
            result["learning_transferred_real"] = "REAL_TOOL_OUTCOME_IMPROVED"
        elif result["real_tool_outcome_delta"] == 0:
            result["learning_transferred_real"] = "NO_OUTCOME_DELTA_OBSERVED"
        else:
            result["learning_transferred_real"] = "REAL_TOOL_OUTCOME_WORSENED"
    finally:
        brain.close()
        runtime.telemetry.stop()
        runtime.store.close()

    if artifact_path is not None:
        artifact_path = Path(artifact_path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(
            json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
        )
    return result
