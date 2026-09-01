"""Tests for L2 MemoryArchive — mark-only archive lifecycle."""
import pytest
from nexara_prime.memory_archive import MemoryArchive, MemoryLifecycle, ArchiveResult


class FakeStore:
    def __init__(self):
        self._records = {}

    def get_record(self, rid):
        return self._records.get(rid)

    def get_record_envelope(self, rid):
        return {"mission_id": "m1"}

    def save_record(self, rid, rtype, payload, created_at=None, mission_id=None):
        self._records[rid] = payload

    def list_records(self, rtype, mission_id=None):
        return [v for v in self._records.values() if v.get("status") is not None]


def _make_active_record(store, mid="mem_001"):
    store._records[mid] = {
        "memory_id": mid,
        "status": "active",
        "version": 1,
        "created_at": "2026-01-01T00:00:00Z",
    }


class TestMemoryArchive:
    def test_archive_active(self):
        store = FakeStore()
        _make_active_record(store)
        ma = MemoryArchive(store)
        result = ma.archive_memory("mem_001", "superseded by v2")
        assert result.status == "archived"
        assert result.version == 2
        assert result.archive_reason == "superseded by v2"

    def test_archive_already_archived_is_idempotent(self):
        store = FakeStore()
        _make_active_record(store)
        ma = MemoryArchive(store)
        r1 = ma.archive_memory("mem_001", "reason1")
        r2 = ma.archive_memory("mem_001", "reason2")
        assert r1.status == r2.status == "archived"
        assert r2.archive_reason == "reason1"

    def test_archive_candidate_rejected(self):
        store = FakeStore()
        store._records["mem_002"] = {"status": "candidate", "version": 1}
        ma = MemoryArchive(store)
        with pytest.raises(ValueError, match="not_archivable"):
            ma.archive_memory("mem_002", "cleanup")

    def test_archive_missing_raises(self):
        ma = MemoryArchive(FakeStore())
        with pytest.raises(KeyError, match="memory_not_found"):
            ma.archive_memory("nonexistent", "x")

    def test_list_active_excludes_archived(self):
        store = FakeStore()
        _make_active_record(store, "mem_a")
        store._records["mem_b"] = {"status": "archived", "version": 2}
        ma = MemoryArchive(store)
        active = ma.list_active()
        assert all(r.get("status") != "archived" for r in active)

    def test_list_archived_only(self):
        store = FakeStore()
        _make_active_record(store, "mem_a")
        store._records["mem_b"] = {"status": "archived", "version": 2}
        ma = MemoryArchive(store)
        archived = ma.list_archived()
        assert all(r.get("status") == "archived" for r in archived)
