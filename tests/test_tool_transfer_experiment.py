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

    assert result["task_b"]["cold"]["success"] is False
    assert result["task_b"]["decision"]["action"] == SAFE_TOOL
    assert result["task_b"]["decision"]["based_on"] >= 2
    assert result["task_b"]["decision"]["based_on_missions"] >= 2
    assert result["task_b"]["experienced"]["success"] is True
    assert result["decision_changed"] is True

    assert result["task_b"]["revoked_decision"]["action"] is None
    assert result["task_b"]["revoked_choice"] == COLD_CHOICE
    assert result["task_b"]["revoked"]["success"] is False
    assert result["decision_reverted"] is True

    assert result["cold_success"] is False
    assert result["experienced_success"] is True
    assert result["real_tool_outcome_delta"] == 1
    assert result["learning_transferred_real"] == "REAL_TOOL_OUTCOME_IMPROVED"

    stored = json.loads(artifact.read_text())
    assert stored["learning_transferred_real"] == "REAL_TOOL_OUTCOME_IMPROVED"
