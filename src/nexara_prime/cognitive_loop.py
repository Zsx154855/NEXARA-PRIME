"""Minimal execution loop: selected goal -> real Runtime Mission -> verified outcome.

This is an isolated MOCK_INTEGRATION experiment: the Runtime uses its mock model.
It exercises the real Mission lifecycle, ToolRuntime receipts and EvidenceStore,
but it is not LIVE_EXTERNAL execution and does not claim production autonomy.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .goal_discovery import GoalCandidate
from .runtime import NexaraRuntime


@dataclass
class ExecutionOutcome:
    goal_id: str
    objective: str
    mission_id: str
    state: str
    evidence_ids: list[str]
    tool_invocations: list[str]
    completed_invocations: list[str]
    report_path: str
    error: str
    mode: str
    approval_actor: str


def execute_goal(goal: GoalCandidate, settings: Settings) -> ExecutionOutcome:
    """Execute one generated goal through the real Runtime Mission lifecycle."""
    runtime = NexaraRuntime(settings)
    try:
        mission = runtime.create_mission(goal.objective)
        runtime.plan_mission(mission.mission_id)
        approval_actor = "cognitive_loop:auto"
        runtime.approve_mission(mission.mission_id, approved=True, actor=approval_actor)
        error = ""
        try:
            runtime.run_mission(mission.mission_id)
        except Exception as exc:  # record terminal failure, do not hide it
            error = f"{type(exc).__name__}: {exc}"
        final = runtime.get_mission(mission.mission_id)
        evidence_ids = [e["evidence_id"] for e in runtime.evidence.list(mission.mission_id)]
        invocations_raw = runtime.tools.list_invocations(mission.mission_id)
        invocations = [str(inv.get("invocation_id", "")) for inv in invocations_raw]
        completed = [
            str(inv.get("invocation_id", ""))
            for inv in invocations_raw if str(inv.get("status", "")) == "completed"
        ]
        return ExecutionOutcome(
            goal_id=goal.goal_id,
            objective=goal.objective,
            mission_id=mission.mission_id,
            state=final.state.value if hasattr(final.state, "value") else str(final.state),
            evidence_ids=evidence_ids,
            tool_invocations=invocations,
            completed_invocations=completed,
            report_path=str(final.result.get("report_path", "")),
            error=error,
            mode="MOCK_INTEGRATION" if runtime.settings.mock_model else "LIVE",
            approval_actor=approval_actor,
        )
    finally:
        runtime.telemetry.stop()
        runtime.store.close()


def verify_outcome(outcome: ExecutionOutcome) -> dict[str, Any]:
    """Independent checks over the execution artifacts, not the goal's self-report."""
    reasons: list[str] = []
    if outcome.state != "Completed":
        reasons.append(f"state_not_completed:{outcome.state}")
    if len(outcome.evidence_ids) < 1:
        reasons.append("no_evidence")
    if not outcome.tool_invocations:
        reasons.append("no_tool_invocations")
    if not outcome.completed_invocations:
        reasons.append("no_completed_tool_invocation")
    if outcome.approval_actor == "human":
        reasons.append("unattributed_human_approval")
    if not outcome.report_path or not Path(outcome.report_path).exists():
        reasons.append("report_missing")
    if outcome.error:
        reasons.append("execution_error")
    return {"passed": not reasons, "reasons": reasons, "mode": outcome.mode}


def record_outcome(path: Path, outcome: ExecutionOutcome, verification: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {"outcome": asdict(outcome), "verification": verification},
            indent=2, sort_keys=True,
        ),
        encoding="utf-8",
    )
    return target


def transfer_control(workdir: Path) -> dict[str, Any]:
    """Run the existing cold/experienced/revoked comparison; synthetic, no provider calls."""
    from .experience_transfer import run_experiment

    result = run_experiment(workdir)
    return {
        "cold_start": result["cold_start"]["success_rate"],
        "experienced": result["experienced"]["success_rate"],
        "after_revocation": result["after_revocation"]["success_rate"],
        "delta_success_rate": result["delta_success_rate"],
        "revocation_effective": result["revocation_effective"],
        "mode": "SYNTHETIC_CONTROL",
        "model_calls": result["cost"]["model_calls"],
        "limits": result["limits"],
    }
