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
        for mission_index in ("1", "2"):
            task_a = runtime.create_mission(f"Tool transfer task A{mission_index}")
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

        cold_mission = runtime.create_mission("Tool transfer task B cold")
        cold_run = _invoke_strategy(
            runtime, cold_mission.mission_id, COLD_CHOICE, "cold"
        )
        result["task_b"]["cold"] = cold_run

        decision = learner.recommend_action("exec")
        experienced_choice = decision.get("action") or COLD_CHOICE
        result["task_b"]["decision"] = decision
        result["task_b"]["experienced_choice"] = experienced_choice
        experienced_mission = runtime.create_mission(
            "Tool transfer task B experienced"
        )
        experienced_run = _invoke_strategy(
            runtime, experienced_mission.mission_id, experienced_choice, "learned"
        )
        result["task_b"]["experienced"] = experienced_run
        result["decision_changed"] = experienced_choice != COLD_CHOICE

        memory_ids = [
            row["memory_id"]
            for row in brain.recall(kind="experience")
            if row.get("status") == "active"
        ]
        for memory_id in memory_ids:
            brain.update_status(memory_id, "archived")
        revoked_decision = learner.recommend_action("exec")
        revoked_choice = revoked_decision.get("action") or COLD_CHOICE
        revoked_mission = runtime.create_mission("Tool transfer task B revoked")
        revoked_run = _invoke_strategy(
            runtime, revoked_mission.mission_id, revoked_choice, "revoked"
        )
        result["task_b"]["revoked_decision"] = revoked_decision
        result["task_b"]["revoked_choice"] = revoked_choice
        result["task_b"]["revoked"] = revoked_run
        result["decision_reverted"] = revoked_choice == COLD_CHOICE

        cold_success = bool(cold_run["success"])
        experienced_success = bool(experienced_run["success"])
        result["cold_success"] = cold_success
        result["experienced_success"] = experienced_success
        result["revoked_success"] = bool(revoked_run["success"])
        result["real_tool_outcome_delta"] = int(experienced_success) - int(cold_success)
        if experienced_success and not cold_success:
            result["learning_transferred_real"] = "REAL_TOOL_OUTCOME_IMPROVED"
        elif experienced_success == cold_success:
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
