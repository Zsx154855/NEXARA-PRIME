"""T6 acceptance: a replayed stage does not append duplicate evidence/memory."""
from __future__ import annotations

from pathlib import Path

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


def test_state_transition_evidence_is_idempotent(tmp_path: Path):
    runtime = _runtime(tmp_path)
    first = runtime.evidence.state_change(
        "mission_x", "Intent", "Context", "trace_x", "evt_1",
        idempotency_key="state-transition:mission_x:Intent->Context",
    )
    second = runtime.evidence.state_change(
        "mission_x", "Intent", "Context", "trace_x", "evt_1",
        idempotency_key="state-transition:mission_x:Intent->Context",
    )
    assert first.evidence_id == second.evidence_id
    rows = [e for e in runtime.evidence.list("mission_x") if e.get("kind") == "state_transition"]
    assert len(rows) == 1, f"expected 1 transition evidence, found {len(rows)}"


def test_memory_os_entry_is_idempotent(tmp_path: Path):
    runtime = _runtime(tmp_path)
    memory = MemoryOS(runtime.store)
    a = memory.create_entry(MemoryType.EPISODIC, "mission.completed_report", "mission_y",
                            idempotency_key="mission_y:memory_episodic")
    b = memory.create_entry(MemoryType.EPISODIC, "mission.completed_report", "mission_y",
                            idempotency_key="mission_y:memory_episodic")
    assert a.memory_id == b.memory_id
    rows = [r for r in runtime.store.list_records("memory") if r.get("memory_id") == a.memory_id]
    assert len(rows) == 1, f"expected 1 memory row, found {len(rows)}"
