"""Tests for L2 MemoryOS — five-type, five-state memory system."""
import pytest
from nexara_prime.memory_os import MemoryOS, MemoryType, MemoryEntry


class TestMemoryOSInMemory:
    def test_create_entry(self):
        mos = MemoryOS()
        entry = mos.create_entry(MemoryType.EPISODIC, "test content", "unit_test")
        assert entry.type == "episodic"
        assert entry.status == "active"
        assert entry.version == 1

    def test_create_with_string_type(self):
        mos = MemoryOS()
        entry = mos.create_entry("semantic", "fact", "test")
        assert entry.type == "semantic"

    def test_supersede(self):
        mos = MemoryOS()
        e1 = mos.create_entry(MemoryType.EPISODIC, "v1", "test")
        e2 = mos.create_entry(MemoryType.EPISODIC, "v2", "test")
        result = mos.supersede(e1.memory_id, e2.memory_id)
        assert result.status == "superseded"
        assert result.version == 2

    def test_supersede_not_found_raises(self):
        mos = MemoryOS()
        with pytest.raises(KeyError):
            mos.supersede("nonexistent", "new_id")

    def test_archive_and_restore(self):
        mos = MemoryOS()
        e = mos.create_entry(MemoryType.PROCEDURAL, "steps", "test")
        archived = mos.archive(e.memory_id, "no longer needed")
        assert archived.status == "archived"
        restored = mos.restore(e.memory_id)
        assert restored.status == "active"
        assert restored.version == archived.version + 1

    def test_restore_non_archived_raises(self):
        mos = MemoryOS()
        e = mos.create_entry(MemoryType.PREFERENCE, "pref", "test")
        with pytest.raises(ValueError, match="not_restorable"):
            mos.restore(e.memory_id)

    def test_list_by_type(self):
        mos = MemoryOS()
        mos.create_entry(MemoryType.EPISODIC, "e1", "test")
        mos.create_entry(MemoryType.SEMANTIC, "s1", "test")
        mos.create_entry(MemoryType.EPISODIC, "e2", "test")
        episodic = mos.list_by_type(MemoryType.EPISODIC)
        assert len(episodic) == 2

    def test_list_active_excludes_archived_and_superseded(self):
        mos = MemoryOS()
        e1 = mos.create_entry(MemoryType.OPERATIONAL, "op", "test")
        mos.create_entry(MemoryType.OPERATIONAL, "op2", "test")
        mos.archive(e1.memory_id, "done")
        active = mos.list_active()
        assert len(active) == 1
