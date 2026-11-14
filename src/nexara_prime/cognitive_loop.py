"""Minimal execution loop: selected goal -> real Runtime Mission -> verified outcome.

This is an isolated MOCK_INTEGRATION experiment: the Runtime uses its mock model.
It exercises the real Mission lifecycle, ToolRuntime receipts and EvidenceStore,
but it is not LIVE_EXTERNAL execution and does not claim production autonomy.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .db import SQLiteStore
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
    """Execute a generated goal only in the isolated zero-provider-cost mock lane."""
    # No implicit live execution: this function self-approves a Mission. A live
    # mode needs a separate authenticated admission path and cost authorization.
    if not settings.mock_model or settings.model_provider.lower() != "mock":
        raise ValueError("cognitive_loop_mock_only")
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


def _verify_persisted(outcome: ExecutionOutcome, settings: Settings) -> list[str]:
    """Read the persisted Runtime record envelopes without starting a new Runtime.

    SQLite URI mode=ro ensures verification does not initialize schemas,
    trigger background recovery or mutate the Runtime's authoritative store.
    """
    if not settings.mock_model or settings.model_provider.lower() != "mock":
        return ["independent_mock_mode_required"]
    if outcome.mode != "MOCK_INTEGRATION":
        return ["execution_mode_mismatch"]
    if not settings.db_path.is_file():
        return ["independent_store_missing"]
    try:
        with closing(sqlite3.connect(settings.db_path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            rows = conn.execute(
                "SELECT record_id, record_type, mission_id, payload, created_at, "
                "integrity_sha256, origin_sha256 FROM records "
                "WHERE mission_id=? OR record_type='audit_entry'",
                (outcome.mission_id,),
            ).fetchall()
    except (OSError, sqlite3.DatabaseError):
        return ["independent_store_unreadable"]

    records: dict[str, dict[str, dict[str, Any]]] = {
        "mission": {}, "tool": {}, "evidence": {}, "audit_entry": {},
    }
    problems: list[str] = []
    for rid, kind, mid, encoded, created, integrity, origin in rows:
        if kind not in records:
            continue
        try:
            payload = json.loads(encoded)
            if not isinstance(payload, dict):
                raise ValueError("record_payload_not_object")
            if kind == "audit_entry" and payload.get("mission_id") != outcome.mission_id:
                continue
            expected = SQLiteStore._record_integrity(rid, kind, mid, created, payload)
            if not integrity or not origin or integrity != expected:
                raise ValueError("record_envelope_integrity")
            if kind == "evidence":
                content = str(payload.get("content", ""))
                if (hashlib.sha256(content.encode("utf-8")).hexdigest() != payload.get("sha256")
                        or SQLiteStore._evidence_envelope_integrity(payload)
                        != payload.get("envelope_sha256")):
                    raise ValueError("evidence_integrity")
            records[kind][rid] = payload
        except (TypeError, ValueError):
            problems.append("independent_record_integrity_invalid")

    mission = records["mission"].get(outcome.mission_id)
    if not mission:
        problems.append("persisted_mission_missing")
    else:
        if mission.get("state") != "Completed" or mission.get("state") != outcome.state:
            problems.append("persisted_state_mismatch")
        if str((mission.get("spec") or {}).get("objective") or "") != outcome.objective:
            problems.append("persisted_objective_mismatch")
        stored_report = str((mission.get("result") or {}).get("report_path") or "")
        if stored_report != outcome.report_path:
            problems.append("persisted_report_mismatch")

    tools = records["tool"]
    evidence = records["evidence"]
    if not tools or set(tools) != set(outcome.tool_invocations):
        problems.append("persisted_tool_invocations_mismatch")
    completed = {
        rid for rid, item in tools.items() if item.get("status") == "completed"
    }
    if not completed or completed != set(outcome.completed_invocations):
        problems.append("persisted_completed_tools_mismatch")
    if not evidence or set(evidence) != set(outcome.evidence_ids):
        problems.append("persisted_evidence_ids_mismatch")
    for rid in completed:
        item = tools[rid]
        eid = item.get("receipt_evidence_id")
        bound = evidence.get(eid)
        if (not bound or bound.get("tool_invocation_id") != rid
                or bound.get("actor") != "tool_runtime"
                or bound.get("verification_status") != "verified"):
            problems.append("tool_receipt_binding_invalid")
            break

    approval_ok = any(
        row.get("event_type") == "approval.decided"
        and row.get("actor_id") == outcome.approval_actor == "cognitive_loop:auto"
        and row.get("actor_type") == "system"
        and row.get("decision") == "approved"
        for row in records["audit_entry"].values()
    )
    if not approval_ok:
        problems.append("persisted_system_approval_missing")

    if outcome.report_path:
        report = Path(outcome.report_path).resolve()
        if not report.is_relative_to(settings.report_root.resolve()):
            problems.append("report_outside_root")
        elif report.is_file():
            receipts = [
                row for row in tools.values()
                if row.get("tool_name") == "file_write_report"
                and row.get("status") == "completed"
                and (row.get("result") or {}).get("path") == str(report)
            ]
            if not receipts or not any(
                (row.get("result") or {}).get("sha256")
                == hashlib.sha256(report.read_bytes()).hexdigest()
                for row in receipts
            ):
                problems.append("report_receipt_digest_mismatch")
    return sorted(set(problems))


def verify_outcome(
    outcome: ExecutionOutcome, settings: Settings | None = None,
) -> dict[str, Any]:
    """Require independent persisted Runtime evidence, not just an outcome DTO."""
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
    if settings is None:
        reasons.append("independent_store_required")
    else:
        reasons.extend(_verify_persisted(outcome, settings))
    return {"passed": not reasons, "reasons": sorted(set(reasons)), "mode": outcome.mode}


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
