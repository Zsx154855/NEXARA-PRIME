"""T7 acceptance: rollback says what it does and does not do."""
from __future__ import annotations

from pathlib import Path

from nexara_prime.config import Settings
from nexara_prime.runtime import NexaraRuntime


def test_rollback_is_explicitly_state_only(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.py").write_text("x = 1\n", encoding="utf-8")
    (source / "b.py").write_text("y = 2\n", encoding="utf-8")

    settings = Settings(
        db_path=tmp_path / "runtime.db",
        workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8895,
    )
    settings.ensure_dirs()
    runtime = NexaraRuntime(settings)

    mission = runtime.create_mission("rollback scope check", str(source))
    runtime.plan_mission(mission.mission_id)
    runtime.approve_mission(mission.mission_id, actor="human")
    done = runtime.run_mission(mission.mission_id)
    assert done.state.value == "Completed"

    rolled = runtime.rollback(mission.mission_id)
    assert rolled.state.value == "RolledBack"
    assert rolled.result.get("rollback_scope") == "state_only"
    assert rolled.result.get("rollback_files_restored") == 0

    evidence = [e for e in runtime.evidence.list(mission.mission_id) if e.get("kind") == "rollback_point"]
    assert evidence, "rollback must leave evidence"
    assert "filesystem content is not restored" in evidence[0].get("content", "")
