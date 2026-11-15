from __future__ import annotations

import json

from nexara_prime.tool_transfer_experiment import (
    COLD_CHOICE,
    FAULTY_TOOL,
    SAFE_TOOL,
    run_tool_transfer,
)


def test_real_tool_transfer_improves_real_outcome(tmp_path):
    artifact = tmp_path / "tool_transfer_result.json"
    result = run_tool_transfer(tmp_path / "run", artifact_path=artifact)

    assert len(result["task_a"]) == 4
    assert all(run["evidence_id"] for run in result["task_a"])
    assert {run["strategy"] for run in result["task_a"]} == {SAFE_TOOL, FAULTY_TOOL}
    assert result["task_a"][0]["status"] == "completed"
    assert result["task_a"][1]["status"] == "failed"
    assert result["task_a"][2]["status"] == "completed"
    assert result["task_a"][3]["status"] == "failed"

    assert result["trials"] == 3
    assert all(run["success"] is False for run in result["task_b"]["cold"])
    assert result["task_b"]["decision"]["action"] == SAFE_TOOL
    assert result["task_b"]["decision"]["based_on"] >= 2
    assert result["task_b"]["decision"]["based_on_missions"] >= 2
    assert all(run["success"] is True for run in result["task_b"]["experienced"])
    assert result["decision_changed"] is True

    assert result["task_b"]["revoked_decision"]["action"] is None
    assert result["task_b"]["revoked_choice"] == COLD_CHOICE
    assert all(run["success"] is False for run in result["task_b"]["revoked"])
    assert result["decision_reverted"] is True

    assert result["cold_success_rate"] == 0.0
    assert result["experienced_success_rate"] == 1.0
    assert result["revoked_success_rate"] == 0.0
    assert result["real_tool_outcome_delta"] == 1.0
    assert result["learning_transferred_real"] == "REAL_TOOL_OUTCOME_IMPROVED"

    stored = json.loads(artifact.read_text())
    assert stored["learning_transferred_real"] == "REAL_TOOL_OUTCOME_IMPROVED"
