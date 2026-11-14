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
    verification = verify_outcome(outcome)
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
