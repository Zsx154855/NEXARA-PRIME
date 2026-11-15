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
    task_a_mission_ids = {run["mission_id"] for run in result["task_a"]}
    assert {event["mission_id"] for event in result["retirement_audit"]} == task_a_mission_ids
    assert all(event["retired"] == 2 for event in result["retirement_audit"])
    assert all(
        event["reason"] == "tool_transfer_experiment_revoked_control"
        for event in result["retirement_audit"]
    )

    assert result["cold_success_rate"] == 0.0
    assert result["experienced_success_rate"] == 1.0
    assert result["revoked_success_rate"] == 0.0
    assert result["real_tool_outcome_delta"] == 1.0
    assert result["learning_transferred_real"] == "REAL_TOOL_OUTCOME_IMPROVED"

    stored = json.loads(artifact.read_text())
    assert stored["learning_transferred_real"] == "REAL_TOOL_OUTCOME_IMPROVED"


def test_revocation_preserves_unrelated_active_experience(tmp_path):
    """The experiment may revoke its own Task A rows, never other missions' rows."""
    from nexara_prime.brain.db import BrainDB
    from nexara_prime.cognitive_loop import _mission_settings
    from nexara_prime.runtime import NexaraRuntime

    workdir = tmp_path / "shared-store-experiment"
    runtime = NexaraRuntime(_mission_settings(workdir))
    brain = BrainDB(store=runtime.store)
    unrelated_id = "mem-unrelated-active-experience"
    unrelated_lesson_id = "mem-unrelated-active-lesson"
    try:
        brain.insert_memory({
            "memory_id": unrelated_id,
            "mission_id": "mission-unrelated",
            "kind": "experience",
            "key": "external:unrelated",
            "content": "{}",
            "status": "active",
        })
        brain.insert_memory({
            "memory_id": unrelated_lesson_id,
            "mission_id": "mission-unrelated",
            "kind": "lesson",
            "key": "lesson:mission-unrelated:unrelated",
            "content": '{"lesson":"preserve unrelated memory"}',
            "status": "active",
        })
    finally:
        brain.close()
        runtime.telemetry.stop()
        runtime.store.close()

    result = run_tool_transfer(workdir)
    assert all(event["retired"] == 2 for event in result["retirement_audit"])
    runtime = NexaraRuntime(_mission_settings(workdir))
    brain = BrainDB(store=runtime.store)
    try:
        untouched = brain.recall(mission_id="mission-unrelated", kind="experience")
        assert [row["memory_id"] for row in untouched] == [unrelated_id]
        untouched_lessons = brain.recall(mission_id="mission-unrelated", kind="lesson")
        assert [row["memory_id"] for row in untouched_lessons] == [unrelated_lesson_id]
        assert not brain.recall(mission_id="mission-unrelated", kind="lesson", status="archived")
        for event in result["retirement_audit"]:
            assert not brain.recall(mission_id=event["mission_id"], kind="experience")
            assert len(
                brain.recall(
                    mission_id=event["mission_id"],
                    kind="experience",
                    status="archived",
                )
            ) == 2
    finally:
        brain.close()
        runtime.telemetry.stop()
        runtime.store.close()


def test_retirement_audit_is_durable_and_scoped_to_task_a(tmp_path):
    """An artifact callback is insufficient: audit events must survive a DB reopen."""
    from nexara_prime.cognitive_loop import _mission_settings
    from nexara_prime.runtime import NexaraRuntime

    workdir = tmp_path / "persistent-retirement-audit"
    result = run_tool_transfer(workdir, artifact_path=tmp_path / "audit-result.json")
    task_a_missions = {row["mission_id"] for row in result["task_a"]}
    assert len(task_a_missions) == 2
    assert len(result["retirement_audit"]) == 2

    runtime = NexaraRuntime(_mission_settings(workdir))
    try:
        for receipt in result["retirement_audit"]:
            mission_id = receipt["mission_id"]
            assert mission_id in task_a_missions
            assert receipt["event_id"]

            events = [
                event for event in runtime.store.list_events(mission_id)
                if event["event_type"] == "experience.retired"
            ]
            assert len(events) == 1
            persisted = events[0]
            assert persisted["event_id"] == receipt["event_id"]
            assert persisted["aggregate_id"] == mission_id
            assert persisted["actor"] == "tool_transfer_experiment"
            assert persisted["idempotency_key"] == f"tool-transfer-retire:{mission_id}"
            assert persisted["payload"]["mission_id"] == mission_id
            assert persisted["payload"]["retired"] == 2
            assert persisted["payload"]["reason"] == (
                "tool_transfer_experiment_revoked_control"
            )

        for runs in (result["task_b"]["cold"], result["task_b"]["experienced"],
                     result["task_b"]["revoked"]):
            for run in runs:
                assert not [
                    event for event in runtime.store.list_events(run["mission_id"])
                    if event["event_type"] == "experience.retired"
                ]
    finally:
        runtime.telemetry.stop()
        runtime.store.close()


def test_update_memory_reports_real_rowcount_and_preserves_input(tmp_path):
    """Nonexistent memory must not inflate the count of retired rows."""
    from nexara_prime.brain.db import BrainDB
    from nexara_prime.cognitive_loop import _mission_settings
    from nexara_prime.runtime import NexaraRuntime

    runtime = NexaraRuntime(_mission_settings(tmp_path / "rowcount"))
    brain = BrainDB(store=runtime.store)
    try:
        payload = {"status": "archived"}
        assert brain.update_memory("mem-does-not-exist", payload) is False
        assert payload == {"status": "archived"}
        brain.insert_memory({
            "memory_id": "mem-existing",
            "mission_id": "mission-existing",
            "kind": "lesson",
            "key": "lesson:real-rowcount",
            "content": "{}",
            "status": "active",
        })
        assert brain.update_status("mem-existing", "archived") is True
        assert [row["memory_id"] for row in brain.recall(
            mission_id="mission-existing", kind="lesson", status="archived",
        )] == ["mem-existing"]
    finally:
        brain.close()
        runtime.telemetry.stop()
        runtime.store.close()


def test_retirement_event_failure_exposes_nonatomic_boundary(tmp_path, monkeypatch):
    """Diagnostic: a failed event write must not be mistaken for a clean audit.

    This test documents a known failure of cross-table atomicity. It DOES NOT
    claim that archival rolls back when an event write fails.
    """
    import pytest
    from nexara_prime.brain.db import BrainDB
    from nexara_prime.cognitive_loop import _mission_settings
    from nexara_prime.events import EventBus
    from nexara_prime.runtime import NexaraRuntime

    workdir = tmp_path / "retirement-event-failure"
    original_publish = EventBus.publish

    def fail_only_retirement(self, event_type, *args, **kwargs):
        if event_type == "experience.retired":
            raise OSError("injected_retirement_event_failure")
        return original_publish(self, event_type, *args, **kwargs)

    monkeypatch.setattr(EventBus, "publish", fail_only_retirement)
    with pytest.raises(OSError, match="injected_retirement_event_failure"):
        run_tool_transfer(workdir)
    monkeypatch.setattr(EventBus, "publish", original_publish)

    runtime = NexaraRuntime(_mission_settings(workdir))
    brain = BrainDB(store=runtime.store)
    try:
        archived = brain.recall(kind="experience", status="archived")
        persisted_events = [
            event for event in runtime.store.list_events()
            if event["event_type"] == "experience.retired"
        ]
        # Known P0 atomicity gap: at least one retirement was persisted,
        # yet its corresponding audit event did not persist.
        assert len(archived) == 2
        assert persisted_events == []
        assert {row["mission_id"] for row in archived} != set()
    finally:
        brain.close()
        runtime.telemetry.stop()
        runtime.store.close()
