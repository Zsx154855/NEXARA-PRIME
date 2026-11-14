"""P2 integration: canonical Runtime evidence -> trusted experience -> next choice."""

from __future__ import annotations

from pathlib import Path

from nexara_prime.runtime_experience_bridge import (
    build_runtime_bridge,
    capture_mission,
    experience_count,
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
