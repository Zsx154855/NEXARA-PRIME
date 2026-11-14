"""COGNITIVE-AUTONOMY-01 stages A/B: real signals -> generated goals -> selection."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

from nexara_prime.goal_discovery import (
    propose_goals,
    record_decision,
    select_goal,
    signals_from_junit,
    signals_from_qa_markdown,
    signals_from_runtime_missions,
)


def test_goals_are_generated_from_real_sources_and_selected_with_rationale(tmp_path):
    # 1) A real failing pytest run produces a real JUnit failure.
    failing = tmp_path / "test_sample.py"
    failing.write_text(textwrap.dedent(
        """
        def test_expected_value():
            assert 2 + 2 == 5
        """
    ))
    junit = tmp_path / "junit.xml"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(failing), f"--junitxml={junit}", "-q"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode != 0
    test_signals = signals_from_junit(junit)
    assert test_signals and test_signals[0].kind == "test_failure"

    # 2) Real failed mission record and QA findings file.
    mission_signals = signals_from_runtime_missions([
        {"mission_id": "m42", "state": "Failed", "spec": {"objective": "write report"},
         "result": {"error": "approval_missing"}},
    ])
    qa = tmp_path / "QA.md"
    qa.write_text("- MED: capture failure path lacks a repo-level test\n- low: no close guard\n")
    qa_signals = signals_from_qa_markdown(qa)
    assert mission_signals and qa_signals

    goals = propose_goals([*test_signals, *mission_signals, *qa_signals])
    assert len(goals) >= 3
    assert all(goal.success_criteria and goal.evidence for goal in goals)

    decision = select_goal(goals)
    assert decision["selected"] is not None
    assert decision["factors"]["score"] > 0
    assert "selected" in decision["rationale"]

    artifact = record_decision(tmp_path / "decision.json", decision)
    stored = json.loads(artifact.read_text())
    assert stored["selected"]["goal_id"] == decision["selected"]["goal_id"]


def test_no_signals_means_no_fabricated_goal(tmp_path):
    assert propose_goals([]) == []
    assert select_goal([])["selected"] is None


def test_runtime_failure_signal_from_real_runtime_store(tmp_path):
    from nexara_prime.config import Settings
    from nexara_prime.runtime import NexaraRuntime

    settings = Settings(
        db_path=tmp_path / "runtime.db", workspace_root=tmp_path / "w",
        report_root=tmp_path / "reports", model_provider="mock", mock_model=True,
        api_host="127.0.0.1", api_port=0,
    )
    settings.ensure_dirs()
    rt = NexaraRuntime(settings)
    try:
        mission = rt.create_mission("Real failed mission signal")
        mission.state = "Failed"
        mission.result["error"] = "approval_missing"
        rt._save_mission(mission)
        signals = signals_from_runtime_missions(rt.list_missions())
        assert len(signals) == 1
        assert signals[0].kind == "mission_failure"
        assert "approval_missing" in signals[0].detail
    finally:
        rt.telemetry.stop()
        rt.store.close()
