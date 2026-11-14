"""P2 integration: canonical Runtime evidence -> trusted experience -> next choice."""

from __future__ import annotations

from pathlib import Path

from nexara_prime.runtime_experience_bridge import (
    build_runtime_bridge,
    capture_mission,
    close_bridge,
    experience_count,
    retire_mission,
    select_objective,
)
from nexara_prime.config import Settings
from nexara_prime.runtime import NexaraRuntime


def _runtime(tmp_path: Path) -> NexaraRuntime:
    settings = Settings(
        db_path=tmp_path / "runtime.db",
        workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=0,
    )
    settings.ensure_dirs()
    return NexaraRuntime(settings)


def _run(rt: NexaraRuntime, objective: str) -> str:
    mission = rt.create_mission(objective)
    rt.plan_mission(mission.mission_id)
    rt.approve_mission(mission.mission_id, approved=True)
    rt.run_mission(mission.mission_id)
    final = rt.get_mission(mission.mission_id)
    assert final.state == "Completed", final.state
    return mission.mission_id


def test_bridge_uses_canonical_store_and_captures_verified_experience(tmp_path):
    rt = _runtime(tmp_path)
    try:
        first = _run(rt, "Write a local repository report")
        bridge = build_runtime_bridge(rt)
        assert bridge.brain._conn is rt.store._conn
        assert bridge.brain.path == rt.store.path

        ids = capture_mission(bridge, first)
        assert ids
        assert experience_count(bridge, first) == len(ids)
        assert bridge.learner.rank_experiences("report")

        # Replay must not duplicate (P0 idempotency through the bridge).
        before = experience_count(bridge, first)
        assert capture_mission(bridge, first) == ids
        assert experience_count(bridge, first) == before
    finally:
        rt.telemetry.stop()
        rt.store.close()


def test_experience_selects_the_next_objective_and_is_reused(tmp_path):
    rt = _runtime(tmp_path)
    try:
        first = _run(rt, "Write a local repository report")
        second_training = _run(rt, "Write another local repository report")
        bridge = build_runtime_bridge(rt)
        capture_mission(bridge, first)
        capture_mission(bridge, second_training)

        choice = select_objective(
            bridge,
            ["write a second engineering report", "execute unrelated command"],
        )
        assert choice["decision"] is not None
        assert choice["objective"] == "write a second engineering report"
        assert choice["decision"]["action"] == "file_write_report"

        second = _run(rt, choice["objective"])
        first_count = experience_count(bridge, first)
        capture_mission(bridge, second)
        assert experience_count(bridge) > first_count

        # The second, unseen mission is also recallable for the next choice.
        choice_again = select_objective(bridge, ["write a third report"])
        assert choice_again["decision"]["action"] == "file_write_report"
    finally:
        rt.telemetry.stop()
        rt.store.close()

def test_close_bridge_leaves_runtime_store_open(tmp_path):
    rt = _runtime(tmp_path)
    try:
        _run(rt, "Write a local repository report")
        bridge = build_runtime_bridge(rt)
        close_bridge(bridge)
        row = rt.store._conn.execute("SELECT 1").fetchone()
        assert row[0] == 1
    finally:
        rt.telemetry.stop()
        rt.store.close()


class _FixedDecisionLearner:
    def __init__(self):
        self.calls: list[str] = []

    def recommend_action(self, objective: str):
        self.calls.append(objective)
        return {
            "action": "report_tool",
            "confidence": 1.0,
            "based_on": 2,
            "based_on_missions": 2,
            "evidence_ids": ["e1", "e2"],
        }


def test_select_objective_tie_keeps_caller_priority():
    from types import SimpleNamespace

    learner = _FixedDecisionLearner()
    bridge = SimpleNamespace(learner=learner)
    first = select_objective(bridge, ["first objective", "second objective"])
    second = select_objective(bridge, ["second objective", "first objective"])
    # Explicit contract: ties keep caller order, so each call returns its first.
    assert first["objective"] == "first objective"
    assert second["objective"] == "second objective"


def test_capture_skips_one_tampered_receipt_and_counts(tmp_path):
    rt = _runtime(tmp_path)
    try:
        mission_id = _run(rt, "Write a local repository report")
        bridge = build_runtime_bridge(rt)
        invocations = [
            inv for inv in rt.tools.list_invocations(mission_id)
            if inv.get("receipt_evidence_id")
        ]
        assert len(invocations) >= 2
        bad = invocations[0]["receipt_evidence_id"]
        with rt.store._lock, rt.store._conn:
            rt.store._conn.execute(
                "UPDATE records SET payload=? WHERE record_id=?", ("{}", bad)
            )

        created = capture_mission(bridge, mission_id)
        assert len(created) == len(invocations) - 1
        assert bridge.rejected_receipts == 1
    finally:
        rt.telemetry.stop()
        rt.store.close()


def test_retire_mission_emits_audit_and_replay_is_not_created(tmp_path):
    rt = _runtime(tmp_path)
    try:
        mission_id = _run(rt, "Write a local repository report")
        bridge = build_runtime_bridge(rt)
        ids = capture_mission(bridge, mission_id)
        assert ids

        retired = retire_mission(
            bridge, mission_id, reason="wrong tool for objective", actor="qa"
        )
        assert retired == len(ids)
        events = [
            event for event in rt.store.list_events(mission_id)
            if event.get("event_type") == "experience.retired"
        ]
        assert events
        payload = events[-1]["payload"]
        assert payload["reason"] == "wrong tool for objective"
        assert payload["actor"] == "qa"

        bridge.already_retired = 0
        assert capture_mission(bridge, mission_id) == []
        assert bridge.already_retired == len(ids)
    finally:
        rt.telemetry.stop()
        rt.store.close()
