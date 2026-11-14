"""P2 isolated check: BrainDB can share the canonical SQLiteStore authority.

No runtime wiring happens here; these tests only prove the adapter shape in a
throwaway database.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nexara_prime.brain.db import BrainDB
from nexara_prime.db import SQLiteStore


def test_brain_db_uses_injected_store_connection(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "authority.db")
    brain = BrainDB(store=store)
    assert brain._store is store
    assert brain.path == store.path
    assert brain._conn is store._conn

    brain.insert_memory({
        "memory_id": "mem-authority-1",
        "mission_id": "mission-1",
        "key": "k",
        "content": "shared authority",
        "kind": "fact",
    })
    assert brain.get_memory("mem-authority-1")["content"] == "shared authority"
    assert not (tmp_path / ".nexara" / "brain_state.db").exists()


def test_brain_db_rejects_mismatched_path() -> None:
    store = SQLiteStore(Path("/tmp/nexara-authority-mismatch.db"))
    try:
        with pytest.raises(ValueError, match="brain_store_path_mismatch"):
            BrainDB(Path("/tmp/other.db"), store=store)
    finally:
        store._conn.close()


def test_default_brain_db_still_owns_its_store(tmp_path: Path) -> None:
    brain = BrainDB(tmp_path / "brain.db")
    assert brain._store.path == brain.path
    assert brain._conn is brain._store._conn
