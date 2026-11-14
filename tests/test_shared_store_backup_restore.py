"""Shared-store adoption safety: canonical DB (with brain tables) backup/restore."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from nexara_prime.brain.db import BrainDB
from nexara_prime.brain.experience_assembly import build_trusted_experience_learner
from nexara_prime.brain.memory_controller import MemoryController
from nexara_prime.config import Settings
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.runtime import NexaraRuntime
from nexara_prime.runtime_experience_bridge import build_runtime_bridge, capture_mission


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


def _run(rt: NexaraRuntime) -> str:
    mission = rt.create_mission("Write a local repository report")
    rt.plan_mission(mission.mission_id)
    rt.approve_mission(mission.mission_id, approved=True)
    rt.run_mission(mission.mission_id)
    assert rt.get_mission(mission.mission_id).state == "Completed"
    return mission.mission_id


def test_canonical_db_with_brain_tables_backs_up_and_restores(tmp_path):
    rt = _runtime(tmp_path)
    backup = tmp_path / "backup.db"
    restored_store = None
    try:
        mission_id = _run(rt)
        bridge = build_runtime_bridge(rt)
        ids = capture_mission(bridge, mission_id)
        assert ids

        source = sqlite3.connect(rt.store.path)
        target = sqlite3.connect(backup)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()

        with sqlite3.connect(backup) as con:
            tables = {
                row[0]
                for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        assert "brain_memories" in tables
        assert "brain_memory_idempotency" in tables

        restore_dir = tmp_path / "restored"
        restore_dir.mkdir()
        restore_path = restore_dir / "restored.db"
        shutil.copy(backup, restore_path)
        restored_store = SQLiteStore(restore_path)
        restored_brain = BrainDB(store=restored_store)
        restored_evidence = EvidenceStore(restored_store, EventBus(restored_store))
        learner = build_trusted_experience_learner(
            MemoryController(db=restored_brain), restored_evidence
        )
        assert learner.rank_experiences("report")

        assert not (tmp_path / ".nexara" / "brain_state.db").exists()
    finally:
        rt.telemetry.stop()
        rt.store.close()
        if restored_store is not None:
            restored_store.close()
