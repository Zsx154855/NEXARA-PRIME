"""Tests for L2 ControlPlane — read-only observation over the store."""
import pytest
from nexara_prime.control_plane import ControlPlane, RECORD_TYPES


class FakeStore:
    def __init__(self, data=None):
        self._data = data or {}

    def list_records(self, record_type, *args):
        return self._data.get(record_type, [])

    def count(self, table):
        return sum(len(v) for v in self._data.values())


class TestControlPlaneSummary:
    def test_empty_store(self):
        cp = ControlPlane(FakeStore())
        result = cp.summary()
        assert result["total"] == 0
        for rt in RECORD_TYPES:
            assert result["records"][rt] == 0

    def test_counts_per_type(self):
        store = FakeStore({
            "mission": [{"id": "m1"}, {"id": "m2"}],
            "memory": [{"id": "mem1"}],
        })
        cp = ControlPlane(store)
        result = cp.summary()
        assert result["records"]["mission"] == 2
        assert result["records"]["memory"] == 1
        assert result["total"] == 3


class TestControlPlaneHealth:
    def test_total_and_distribution(self):
        store = FakeStore({
            "mission": [{"id": "m1"}],
            "session": [{"id": "s1"}, {"id": "s2"}],
        })
        cp = ControlPlane(store)
        h = cp.health()
        assert h["total_records"] == 3
        assert "mission" in h["record_type_distribution"]
