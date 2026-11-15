"""COGNITIVE-AUTONOMY-02/03: real Mission execution, store-bound verification, transfer."""

from __future__ import annotations

import json
from pathlib import Path

from nexara_prime.cognitive_loop import (
    ExecutionOutcome,
    execute_goal,
    record_outcome,
    run_real_transfer,
    transfer_control,
    verify_outcome,
)
from nexara_prime.config import Settings
from nexara_prime.db import SQLiteStore
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


def _failed_signals(tmp_path: Path):
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


def _verified(tmp_path: Path):
    settings = _settings(tmp_path)
    goal = select_goal(propose_goals(_failed_signals(tmp_path)))["selected"]
    outcome = execute_goal(GoalCandidate(**goal), settings)
    store = SQLiteStore(settings.db_path)
    verification = verify_outcome(outcome, store=store, report_root=settings.report_root)
    return settings, store, outcome, verification


def test_selected_goal_executes_and_is_store_verified(tmp_path):
    settings, store, outcome, verification = _verified(tmp_path)
    try:
        assert outcome.state == "Completed"
        assert verification["passed"], verification["reasons"]
        assert verification["valid_evidence"] >= 1
        assert verification["valid_completed_invocations"] >= 1
        assert "approval_actor_is_label_not_authenticated" in verification["warnings"]
        assert outcome.mode == "MOCK_INTEGRATION"

        approvals = [
            entry for entry in store.list_records("audit_entry")
            if entry.get("event_type") == "approval.decided"
        ]
        assert approvals[-1]["actor_id"] == "cognitive_loop:test_harness"
        assert approvals[-1]["actor_type"] == "system"

        artifact = record_outcome(tmp_path / "outcome.json", outcome, verification)
        assert json.loads(artifact.read_text())["verification"]["passed"] is True
    finally:
        store.close()


def test_forged_and_cross_mission_claims_are_rejected(tmp_path):
    settings, store, outcome, _ = _verified(tmp_path)
    try:
        forged = ExecutionOutcome(**{**outcome.__dict__})
        forged.evidence_ids = ["evidence_forged"]
        forged.tool_invocations = ["tool_forged"]
        forged.completed_invocations = ["tool_forged"]
        verification = verify_outcome(forged, store=store, report_root=settings.report_root)
        assert not verification["passed"]
        assert "evidence_not_found:evidence_forged" in verification["reasons"]
        assert "tool_invocation_not_found:tool_forged" in verification["reasons"]

        cross = ExecutionOutcome(**{**outcome.__dict__})
        cross.evidence_ids = [outcome.evidence_ids[0]]
        cross.mission_id = "mission_nonexistent"
        verification = verify_outcome(cross, store=store, report_root=settings.report_root)
        assert not verification["passed"]
        assert "mission_not_found" in verification["reasons"]
    finally:
        store.close()


def test_unrelated_report_and_failed_mission_are_rejected(tmp_path):
    settings, store, outcome, _ = _verified(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("not the mission report", encoding="utf-8")
    try:
        fake = ExecutionOutcome(**{**outcome.__dict__})
        fake.report_path = str(outside)
        verification = verify_outcome(fake, store=store, report_root=settings.report_root)
        assert not verification["passed"]
        assert any(
            reason in verification["reasons"]
            for reason in ("report_mission_mismatch", "report_outside_root")
        )

        failed = ExecutionOutcome(
            goal_id="G", objective="x", mission_id="missing", state="Completed",
            evidence_ids=[], tool_invocations=[], completed_invocations=[],
            report_path="", error="", mode="MOCK_INTEGRATION",
            approval_actor="human", approval_source="test",
        )
        verification = verify_outcome(failed, store=store, report_root=settings.report_root)
        assert verification["passed"] is False
        assert "mission_not_found" in verification["reasons"]
    finally:
        store.close()


def test_replay_creates_distinct_verified_missions(tmp_path):
    settings = _settings(tmp_path)
    goal = select_goal(propose_goals(_failed_signals(tmp_path)))["selected"]
    goal_obj = GoalCandidate(**goal)
    first = execute_goal(goal_obj, settings)
    second = execute_goal(goal_obj, settings)
    assert first.mission_id != second.mission_id
    store = SQLiteStore(settings.db_path)
    try:
        for outcome in (first, second):
            verification = verify_outcome(
                outcome, store=store, report_root=settings.report_root
            )
            assert verification["passed"], verification["reasons"]
            assert len(set(outcome.evidence_ids)) == len(outcome.evidence_ids)
    finally:
        store.close()


def test_verification_rejects_incomplete_outcome(tmp_path):
    store = SQLiteStore(tmp_path / "empty.db")
    try:
        outcome = ExecutionOutcome(
            goal_id="G001", objective="x", mission_id="missing", state="Failed",
            evidence_ids=[], tool_invocations=[], completed_invocations=[],
            report_path="", error="boom", mode="MOCK_INTEGRATION",
            approval_actor="human", approval_source="test",
        )
        verification = verify_outcome(outcome, store=store)
        assert verification["passed"] is False
        assert "mission_not_found" in verification["reasons"]
        assert "no_valid_evidence" in verification["reasons"]
        assert "no_valid_completed_tool_invocation" in verification["reasons"]
        assert "approval_audit_missing" in verification["reasons"]
    finally:
        store.close()


def test_transfer_control_reports_synthetic_three_arms(tmp_path):
    metrics = transfer_control(tmp_path)
    assert metrics["mode"] == "SYNTHETIC_CONTROL"
    assert (metrics["cold_start"], metrics["experienced"], metrics["after_revocation"]) == (0.0, 1.0, 0.0)
    assert metrics["delta_success_rate"] == 1.0
    assert metrics["model_calls"] == 0


def test_real_transfer_runs_three_real_missions_and_changes_decision(tmp_path):
    result = run_real_transfer(tmp_path)
    assert result["mode"] == "MOCK_INTEGRATION"
    assert len(result["arms"]["task_a"]) == 2
    assert all(result["arms"]["captured"].values())
    assert result["cold"]["objective"] == result["arms"]["candidates"][1]
    assert result["experienced"]["objective"] == result["arms"]["candidates"][0]
    assert result["decision_changed"] is True
    assert result["decision_reverted"] is True
    assert result["all_outcomes_verified"] is True
    assert result["learning_transferred_real"] == "NO_OUTCOME_DELTA_OBSERVED"


def test_live_mode_is_rejected(tmp_path):
    store = SQLiteStore(tmp_path / "empty.db")
    try:
        outcome = ExecutionOutcome(
            goal_id="G", objective="x", mission_id="m", state="Completed",
            evidence_ids=[], tool_invocations=[], completed_invocations=[],
            report_path="", error="", mode="LIVE",
        )
        verification = verify_outcome(outcome, store=store)
        assert verification["passed"] is False
        assert "mode_not_authorized:LIVE" in verification["reasons"]
    finally:
        store.close()


def test_execute_goal_refuses_non_mock_settings(tmp_path):
    import pytest

    from dataclasses import replace

    settings = replace(_settings(tmp_path), mock_model=False)
    goal = GoalCandidate(
        goal_id="G1", objective="x", source="test", kind="test_failure",
        success_criteria="x", value_hypothesis="x", risk="x",
        estimated_cost="x", dependencies=(), evidence="x",
    )
    with pytest.raises(PermissionError, match="live_execution_not_authorized"):
        execute_goal(goal, settings)
