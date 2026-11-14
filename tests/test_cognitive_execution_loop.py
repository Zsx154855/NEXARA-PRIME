"""COGNITIVE-AUTONOMY-02: selected goal -> real Runtime Mission -> verified outcome."""

from __future__ import annotations

import json
from pathlib import Path

from nexara_prime.cognitive_loop import (
    execute_goal,
    record_outcome,
    transfer_control,
    verify_outcome,
)
from nexara_prime.config import Settings
from nexara_prime.goal_discovery import (
    GoalCandidate,
    propose_goals,
    select_goal,
    signals_from_runtime_missions,
)
from nexara_prime.models import MissionState
from nexara_prime.runtime import NexaraRuntime


def _settings(tmp_path: Path) -> Settings:
    settings = Settings(
        db_path=tmp_path / "runtime.db", workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports", model_provider="mock", mock_model=True,
        api_host="127.0.0.1", api_port=0,
    )
    settings.ensure_dirs()
    return settings


def _failed_mission_signals(tmp_path: Path):
    settings = _settings(tmp_path)
    runtime = NexaraRuntime(settings)
    try:
        mission = runtime.create_mission("real failed mission signal")
        mission.state = MissionState.FAILED
        mission.result["error"] = "approval_missing"
        runtime._save_mission(mission)
        return signals_from_runtime_missions(runtime.list_missions())
    finally:
        runtime.telemetry.stop()
        runtime.store.close()


def test_selected_goal_executes_and_is_independently_verified(tmp_path):
    signals = _failed_mission_signals(tmp_path)
    goal = select_goal(propose_goals(signals))["selected"]
    assert goal is not None

    settings = _settings(tmp_path)
    outcome = execute_goal(GoalCandidate(**goal), settings)
    verification = verify_outcome(outcome, settings)
    assert outcome.state == "Completed"
    assert outcome.evidence_ids
    assert outcome.tool_invocations
    assert outcome.completed_invocations
    assert outcome.approval_actor == "cognitive_loop:auto"
    assert verification["passed"], verification["reasons"]
    assert outcome.mode == "MOCK_INTEGRATION"

    artifact = record_outcome(tmp_path / "outcome.json", outcome, verification)
    stored = json.loads(artifact.read_text())
    assert stored["verification"]["passed"] is True

    from nexara_prime.db import SQLiteStore
    store = SQLiteStore(settings.db_path)
    try:
        approvals = [
            entry for entry in store.list_records("audit_entry")
            if entry.get("event_type") == "approval.decided"
        ]
        assert approvals
        assert approvals[-1]["actor_id"] == "cognitive_loop:auto"
        assert approvals[-1]["actor_type"] == "system"
    finally:
        store.close()


def test_verification_rejects_incomplete_outcome(tmp_path):
    from nexara_prime.cognitive_loop import ExecutionOutcome

    outcome = ExecutionOutcome(
        goal_id="G001", objective="x", mission_id="m", state="Failed",
        evidence_ids=[], tool_invocations=[], completed_invocations=[],
        report_path="", error="boom", mode="MOCK_INTEGRATION",
        approval_actor="human",
    )
    verification = verify_outcome(outcome)
    assert verification["passed"] is False
    assert "state_not_completed:Failed" in verification["reasons"]
    assert "no_evidence" in verification["reasons"]
    assert "unattributed_human_approval" in verification["reasons"]


def test_transfer_control_reports_three_arms(tmp_path):
    metrics = transfer_control(tmp_path)
    assert metrics["mode"] == "SYNTHETIC_CONTROL"
    assert metrics["cold_start"] == 0.0
    assert metrics["experienced"] == 1.0
    assert metrics["after_revocation"] == 0.0
    assert metrics["delta_success_rate"] == 1.0
    assert metrics["model_calls"] == 0


def test_completed_self_report_is_not_independent_verification(tmp_path):
    """A self-asserted DTO cannot pass without independent persisted evidence."""
    from dataclasses import replace

    signals = _failed_mission_signals(tmp_path)
    goal = select_goal(propose_goals(signals))["selected"]
    settings = _settings(tmp_path)
    outcome = execute_goal(GoalCandidate(**goal), settings)
    assert verify_outcome(outcome, settings)["passed"]

    detached = verify_outcome(outcome)
    assert not detached["passed"]
    assert "independent_store_required" in detached["reasons"]

    fabricated = replace(outcome, evidence_ids=["fake"], completed_invocations=["fake"])
    result = verify_outcome(fabricated, settings)
    assert not result["passed"]
    assert "persisted_evidence_ids_mismatch" in result["reasons"]
    assert "persisted_completed_tools_mismatch" in result["reasons"]


def test_independent_verifier_rejects_corrupt_stored_mission(tmp_path):
    """Direct SQLite payload tampering must not pass persisted Mission verification."""
    import sqlite3

    signals = _failed_mission_signals(tmp_path)
    goal = select_goal(propose_goals(signals))["selected"]
    settings = _settings(tmp_path)
    outcome = execute_goal(GoalCandidate(**goal), settings)
    assert verify_outcome(outcome, settings)["passed"]

    with sqlite3.connect(settings.db_path) as conn:
        row = conn.execute(
            "SELECT payload FROM records WHERE record_id=?", (outcome.mission_id,),
        ).fetchone()
        stored = json.loads(row[0])
        stored["state"] = "Failed"
        conn.execute(
            "UPDATE records SET payload=? WHERE record_id=?",
            (json.dumps(stored, sort_keys=True), outcome.mission_id),
        )
    result = verify_outcome(outcome, settings)
    assert not result["passed"]
    assert "independent_record_integrity_invalid" in result["reasons"]


def test_independent_verifier_rejects_report_tampering(tmp_path):
    """An existing report is insufficient without the actual tool-result digest."""
    signals = _failed_mission_signals(tmp_path)
    goal = select_goal(propose_goals(signals))["selected"]
    settings = _settings(tmp_path)
    outcome = execute_goal(GoalCandidate(**goal), settings)
    assert verify_outcome(outcome, settings)["passed"]

    Path(outcome.report_path).write_text("tampered after execution", encoding="utf-8")
    result = verify_outcome(outcome, settings)
    assert not result["passed"]
    assert "report_receipt_digest_mismatch" in result["reasons"]


def test_cognitive_self_approval_cannot_run_with_live_provider(tmp_path):
    """Fail before Runtime construction, before any key access or provider call."""
    from dataclasses import replace
    import pytest

    settings = replace(_settings(tmp_path), mock_model=False, model_provider="deepseek")
    goal = GoalCandidate(
        goal_id="LIVE01", objective="run a live tool", source="test", kind="test_failure",
        success_criteria="tool invoked", value_hypothesis="test",
        risk="test", estimated_cost="zero", dependencies=(), evidence="test",
    )
    assert not settings.db_path.exists()
    with pytest.raises(ValueError, match="cognitive_loop_mock_only"):
        execute_goal(goal, settings)
    assert not settings.db_path.exists()
