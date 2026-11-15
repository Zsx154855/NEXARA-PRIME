"""Isolated cognitive execution loop: goal -> real Mission -> store-bound verification.

MOCK_INTEGRATION only. The Runtime runs with mock_model; no LIVE provider call is
authorized here. Verification reads the canonical SQLiteStore/EvidenceStore and
does not trust the submitted ExecutionOutcome fields alone.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .db import SQLiteStore
from .events import EventBus
from .evidence import EvidenceStore
from .brain.experience_learner import TRUSTED_VERIFIER_ACTORS
from .goal_discovery import GoalCandidate
from .models import MissionState
from .runtime import NexaraRuntime

MOCK_ONLY = "MOCK_INTEGRATION"


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
    approval_actor: str = "cognitive_loop:test_harness"
    approval_source: str = "test_harness"


def _mission_settings(workdir: Path) -> Settings:
    settings = Settings(
        db_path=workdir / "runtime.db", workspace_root=workdir / "workspace",
        report_root=workdir / "reports", model_provider="mock", mock_model=True,
        api_host="127.0.0.1", api_port=0,
    )
    settings.ensure_dirs()
    return settings


def _run_mission(runtime: NexaraRuntime, objective: str) -> tuple[str, str]:
    mission = runtime.create_mission(objective)
    runtime.plan_mission(mission.mission_id)
    runtime.approve_mission(
        mission.mission_id, approved=True, actor="cognitive_loop:test_harness"
    )
    error = ""
    try:
        runtime.run_mission(mission.mission_id)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    return mission.mission_id, error


def _outcome(runtime: NexaraRuntime, mission_id: str, goal_id: str, error: str) -> ExecutionOutcome:
    final = runtime.get_mission(mission_id)
    invocations = runtime.tools.list_invocations(mission_id)
    evidence_ids = [e["evidence_id"] for e in runtime.evidence.list(mission_id)]
    return ExecutionOutcome(
        goal_id=goal_id, objective=final.spec.objective, mission_id=mission_id,
        state=final.state.value if hasattr(final.state, "value") else str(final.state),
        evidence_ids=evidence_ids,
        tool_invocations=[str(i.get("invocation_id", "")) for i in invocations],
        completed_invocations=[
            str(i.get("invocation_id", ""))
            for i in invocations if str(i.get("status", "")) == "completed"
        ],
        report_path=str(final.result.get("report_path", "")),
        error=error, mode=MOCK_ONLY,
        approval_actor="cognitive_loop:test_harness",
        approval_source="test_harness",
    )


def execute_goal(goal: GoalCandidate, settings: Settings) -> ExecutionOutcome:
    """Run one goal as a real Mission; refuse anything but the mock integration mode."""
    if not settings.mock_model:
        raise PermissionError("live_execution_not_authorized")
    runtime = NexaraRuntime(settings)
    try:
        mission = runtime.create_mission(goal.objective)
        runtime.plan_mission(mission.mission_id)
        runtime.approve_mission(
            mission.mission_id, approved=True, actor="cognitive_loop:test_harness"
        )
        error = ""
        try:
            runtime.run_mission(mission.mission_id)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        return _outcome(runtime, mission.mission_id, goal.goal_id, error)
    finally:
        runtime.telemetry.stop()
        runtime.store.close()


def verify_outcome(
    outcome: ExecutionOutcome,
    *,
    store: SQLiteStore,
    report_root: Path | None = None,
) -> dict[str, Any]:
    """Check submitted claims against canonical mission/evidence/tool/report records."""
    reasons: list[str] = []
    warnings: list[str] = []
    if outcome.mode != MOCK_ONLY:
        reasons.append(f"mode_not_authorized:{outcome.mode}")

    mission_env = store.get_record_envelope(outcome.mission_id)
    mission = mission_env["payload"] if mission_env and mission_env.get("record_type") == "mission" else None
    expected_report = ""
    if mission is None:
        reasons.append("mission_not_found")
    else:
        if mission.get("state") != MissionState.COMPLETED.value:
            reasons.append(f"mission_state_not_completed:{mission.get('state')}")
        if mission.get("spec", {}).get("objective") != outcome.objective:
            reasons.append("objective_mismatch")
        expected_report = str((mission.get("result") or {}).get("report_path", ""))

    evidence = EvidenceStore(store, EventBus(store))
    valid_evidence = 0
    for evidence_id in outcome.evidence_ids:
        try:
            artifact = evidence.get_by_id(evidence_id)
        except (KeyError, ValueError, RuntimeError):
            reasons.append(f"evidence_not_found:{evidence_id}")
            continue
        if artifact.mission_id != outcome.mission_id:
            reasons.append(f"evidence_cross_mission:{evidence_id}")
            continue
        if not evidence.is_preverified_and_integrity_bound(evidence_id):
            reasons.append(f"evidence_not_preverified:{evidence_id}")
            continue
        if artifact.kind == "execution_receipt" and not evidence.is_trusted_verified(
            evidence_id, trusted_actors=TRUSTED_VERIFIER_ACTORS
        ):
            reasons.append(f"evidence_not_trusted:{evidence_id}")
            continue
        valid_evidence += 1
    if valid_evidence < 1:
        reasons.append("no_valid_evidence")

    tool_rows = {str(row.get("invocation_id")): row for row in store.list_records("tool", outcome.mission_id)}
    valid_completed = 0
    for invocation_id in outcome.tool_invocations:
        row = tool_rows.get(invocation_id)
        if row is None:
            reasons.append(f"tool_invocation_not_found:{invocation_id}")
            continue
        if row.get("mission_id") != outcome.mission_id:
            reasons.append(f"tool_cross_mission:{invocation_id}")
    for invocation_id in outcome.completed_invocations:
        row = tool_rows.get(invocation_id)
        if row is None or row.get("status") != "completed":
            reasons.append(f"completed_invocation_invalid:{invocation_id}")
        else:
            valid_completed += 1
    if valid_completed < 1:
        reasons.append("no_valid_completed_tool_invocation")

    report = Path(outcome.report_path) if outcome.report_path else None
    if report is None or not report.is_file() or report.stat().st_size == 0:
        reasons.append("report_missing_or_empty")
    elif outcome.mission_id not in str(report):
        reasons.append("report_mission_mismatch")
    elif expected_report and report.resolve() != Path(expected_report).resolve():
        reasons.append("report_path_mismatch")
    elif report_root is None:
        reasons.append("report_root_required")
    else:
        try:
            report.resolve().relative_to(Path(report_root).resolve())
        except ValueError:
            reasons.append("report_outside_root")
        verification_evidence = [
            row for row in store.list_records("evidence", outcome.mission_id)
            if row.get("kind") == "verification_report"
        ]
        expected_hash = ""
        if verification_evidence:
            try:
                expected_hash = str(json.loads(verification_evidence[-1].get("content", "{}")).get("sha256", ""))
            except (TypeError, ValueError):
                expected_hash = ""
        if not expected_hash:
            reasons.append("report_evidence_missing")
        elif hashlib.sha256(report.read_bytes()).hexdigest() != expected_hash:
            reasons.append("report_hash_mismatch")

    approvals = [
        row for row in store.list_records("audit_entry")
        if row.get("event_type") == "approval.decided"
        and row.get("mission_id") == outcome.mission_id
    ]
    approval = approvals[-1] if approvals else None
    if approval is None:
        reasons.append("approval_audit_missing")
    else:
        if approval.get("actor_id") != outcome.approval_actor:
            reasons.append("approval_actor_mismatch")
        if approval.get("actor_type") != "system":
            reasons.append("approval_actor_type_not_system")
        if approval.get("decision") != "approved":
            reasons.append("approval_decision_not_approved")
        warnings.append("approval_actor_is_label_not_authenticated")
    if outcome.error:
        reasons.append("execution_error")

    return {
        "passed": not reasons, "reasons": reasons, "warnings": warnings,
        "mode": outcome.mode, "valid_evidence": valid_evidence,
        "valid_completed_invocations": valid_completed,
    }


def record_outcome(path: Path, outcome: ExecutionOutcome, verification: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"outcome": asdict(outcome), "verification": verification},
                   indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return target


def transfer_control(workdir: Path) -> dict[str, Any]:
    """Synthetic three-arm control (kept as a labelled comparison, not real transfer)."""
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


def run_real_transfer(workdir: Path) -> dict[str, Any]:
    """Real local Mission A -> trusted experience -> real Mission B, three arms.

    Cold choice is frozen to candidate[1]. Experienced selection uses only the
    verified experiences captured from Task A; revoked retires those first.
    Outcomes are verified from the canonical store. This is still MOCK_INTEGRATION.
    """
    from .runtime_experience_bridge import (
        build_runtime_bridge, capture_mission, retire_mission, select_objective,
    )

    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    settings = _mission_settings(workdir)
    task_a = ["Write a repository report A1", "Write a repository report A2"]
    candidates = ["Write an unseen report B", "Run an unrelated execution check"]
    arms: dict[str, Any] = {"task_a": [], "candidates": candidates, "cold_choice": candidates[1]}

    for objective in task_a:
        runtime = NexaraRuntime(settings)
        try:
            mission_id, error = _run_mission(runtime, objective)
            arms["task_a"].append(
                {"objective": objective, "mission_id": mission_id, "error": error}
            )
        finally:
            runtime.telemetry.stop()
            runtime.store.close()

    # Capture verified experiences into the same canonical store.
    runtime = NexaraRuntime(settings)
    try:
        bridge = build_runtime_bridge(runtime)
        captured = {
            item["mission_id"]: capture_mission(bridge, item["mission_id"])
            for item in arms["task_a"]
        }
    finally:
        runtime.telemetry.stop()
        runtime.store.close()
    arms["captured"] = {key: len(value) for key, value in captured.items()}

    def _execute(choice: str) -> dict[str, Any]:
        runtime = NexaraRuntime(settings)
        try:
            mission_id, error = _run_mission(runtime, choice)
            outcome = _outcome(runtime, mission_id, "B", error)
            verification = verify_outcome(
                outcome, store=SQLiteStore(settings.db_path),
                report_root=settings.report_root,
            )
            return {"objective": choice, "outcome": asdict(outcome), "verification": verification}
        finally:
            runtime.telemetry.stop()
            runtime.store.close()

    cold = _execute(candidates[1])

    def _choose_or_cold() -> str:
        runtime = NexaraRuntime(settings)
        try:
            bridge = build_runtime_bridge(runtime)
            selected = select_objective(bridge, candidates)
            return selected["objective"] if selected["decision"] is not None else candidates[1]
        finally:
            runtime.telemetry.stop()
            runtime.store.close()

    choice = _choose_or_cold()
    experienced = _execute(choice)

    runtime = NexaraRuntime(settings)
    try:
        bridge = build_runtime_bridge(runtime)
        for item in arms["task_a"]:
            retire_mission(bridge, item["mission_id"], reason="transfer control revocation")
    finally:
        runtime.telemetry.stop()
        runtime.store.close()
    choice_after = _choose_or_cold()
    revoked = _execute(choice_after)

    return {
        "mode": MOCK_ONLY,
        "arms": arms,
        "cold": cold,
        "experienced": experienced,
        "revoked": revoked,
        "decision_changed": experienced["objective"] != cold["objective"],
        "decision_reverted": revoked["objective"] == cold["objective"],
        "all_outcomes_verified": all(
            arm["verification"]["passed"] for arm in (cold, experienced, revoked)
        ),
        "learning_transferred_real": "NO_OUTCOME_DELTA_OBSERVED",
        "limitations": (
            "Mock model; all three real missions complete, so only decision influence "
            "is measured. Not LIVE_EXTERNAL and not business-level learning."
        ),
        "timestamp": time.time(),
    }
