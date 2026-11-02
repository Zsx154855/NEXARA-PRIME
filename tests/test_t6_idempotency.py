"""T6 acceptance: crash-replay of a state transition must not poison the mission."""
from __future__ import annotations

from pathlib import Path

import pytest

from nexara_prime.config import Settings
from nexara_prime.memory_os import MemoryOS, MemoryType
from nexara_prime.runtime import NexaraRuntime


def _runtime(tmp_path: Path) -> NexaraRuntime:
    settings = Settings(
        db_path=tmp_path / "runtime.db",
        workspace_root=tmp_path / "workspace",
        report_root=tmp_path / "reports",
        model_provider="mock",
        mock_model=True,
        api_host="127.0.0.1",
        api_port=8894,
    )
    settings.ensure_dirs()
    return NexaraRuntime(settings)


def test_state_transition_survives_crash_and_replay(tmp_path: Path):
    """Evidence is written, the save is interrupted, then the transition is retried.

    With a (from,to) idempotency key the replay raises evidence_idempotency_conflict
    and run_mission would mark the mission FAILED forever. The key must follow the
    transition *event*, not the state pair.
    """
    from nexara_prime.models import MissionState

    runtime = _runtime(tmp_path)
    mission = runtime.create_mission("replay check")

    original_save = runtime._save_mission

    def crash(_mission):
        raise KeyboardInterrupt

    runtime._save_mission = crash
    with pytest.raises(KeyboardInterrupt):
        runtime._advance(mission, MissionState.CONTEXT, "test")
    runtime._save_mission = original_save

    reloaded = runtime.get_mission(mission.mission_id)
    assert reloaded.state == "Intent", "the interrupted save must not advance the stored state"

    runtime._advance(reloaded, MissionState.CONTEXT, "test")  # must not raise
    assert runtime.get_mission(mission.mission_id).state == "Context"

    transitions = [e for e in runtime.evidence.list(mission.mission_id)
                   if e.get("kind") == "state_transition"]
    assert len(transitions) == 2, f"expected both attempts recorded, found {len(transitions)}"


def test_memory_os_entry_is_idempotent(tmp_path: Path):
    runtime = _runtime(tmp_path)
    memory = MemoryOS(runtime.store)
    a = memory.create_entry(MemoryType.EPISODIC, "mission.completed_report", "mission_y",
                            idempotency_key="mission_y:memory_episodic")
    b = memory.create_entry(MemoryType.EPISODIC, "mission.completed_report", "mission_y",
                            idempotency_key="mission_y:memory_episodic")
    assert a.memory_id == b.memory_id
    rows = [r for r in runtime.store.list_records("memory") if r.get("memory_id") == a.memory_id]
    assert len(rows) == 1
