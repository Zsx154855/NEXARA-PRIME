"""Tests for intelligence.failure_database — FailureCategory / FailureRecord / FailureDatabase."""
from __future__ import annotations

import pytest

from nexara_prime.intelligence.failure_database import (
    FailureCategory,
    FailureDatabase,
    FailureRecord,
)


class TestFailureCategory:
    def test_all_nine_categories_exist(self):
        assert len(FailureCategory) == 9

    def test_values_are_strings(self):
        for cat in FailureCategory:
            assert isinstance(cat.value, str)

    def test_construct_from_value(self):
        assert FailureCategory("planning") is FailureCategory.PLANNING


class TestFailureRecord:
    def test_defaults(self):
        rec = FailureRecord(category=FailureCategory.TOOL)
        assert rec.category is FailureCategory.TOOL
        assert rec.context == ""
        assert rec.failure_id.startswith("failure_")
        assert rec.timestamp

    def test_as_dict_round_trip(self):
        rec = FailureRecord(
            category=FailureCategory.COST,
            context="mission-42",
            trigger="budget_exceeded",
            root_cause="unbounded loop",
            recovery_action="circuit_break",
            final_result="partial",
            lesson="cap iterations",
        )
        d = rec.as_dict()
        assert d["category"] == "cost"
        assert d["context"] == "mission-42"
        assert d["lesson"] == "cap iterations"
        assert "failure_id" in d
        assert "timestamp" in d


class TestFailureDatabase:
    def test_empty_database(self):
        db = FailureDatabase()
        assert db.count() == 0
        assert db.categories_present() == []
        assert db.to_dicts() == []

    def test_record_and_count(self):
        db = FailureDatabase()
        db.record(FailureRecord(category=FailureCategory.PLANNING))
        db.record(FailureRecord(category=FailureCategory.TOOL))
        assert db.count() == 2

    def test_by_category_filters(self):
        db = FailureDatabase()
        db.record(FailureRecord(category=FailureCategory.PLANNING))
        db.record(FailureRecord(category=FailureCategory.TOOL))
        db.record(FailureRecord(category=FailureCategory.PLANNING))
        planning = db.by_category(FailureCategory.PLANNING)
        assert len(planning) == 2
        assert all(r.category is FailureCategory.PLANNING for r in planning)

    def test_by_category_empty(self):
        db = FailureDatabase()
        db.record(FailureRecord(category=FailureCategory.TOOL))
        assert db.by_category(FailureCategory.MEMORY) == []

    def test_categories_present_sorted(self):
        db = FailureDatabase()
        db.record(FailureRecord(category=FailureCategory.RECOVERY))
        db.record(FailureRecord(category=FailureCategory.COST))
        db.record(FailureRecord(category=FailureCategory.PLANNING))
        assert db.categories_present() == ["cost", "planning", "recovery"]

    def test_to_dicts(self):
        db = FailureDatabase()
        db.record(FailureRecord(category=FailureCategory.DECISION, trigger="bad_branch"))
        dicts = db.to_dicts()
        assert len(dicts) == 1
        assert dicts[0]["trigger"] == "bad_branch"
        assert dicts[0]["category"] == "decision"

    def test_record_returns_same_record(self):
        db = FailureDatabase()
        rec = FailureRecord(category=FailureCategory.GOVERNANCE)
        returned = db.record(rec)
        assert returned is rec

    def test_invalid_category_raises(self):
        with pytest.raises(ValueError):
            FailureCategory("nonexistent")

    def test_unique_failure_ids(self):
        ids = {FailureRecord(category=FailureCategory.TOOL).failure_id for _ in range(50)}
        assert len(ids) == 50

    def test_by_category_returns_detached_list(self):
        db = FailureDatabase()
        rec = FailureRecord(category=FailureCategory.PLANNING)
        db.record(rec)
        result = db.by_category(FailureCategory.PLANNING)
        result.clear()
        assert db.by_category(FailureCategory.PLANNING) == [rec]

    def test_insertion_order_preserved_in_to_dicts(self):
        db = FailureDatabase()
        db.record(FailureRecord(category=FailureCategory.COST, trigger="first"))
        db.record(FailureRecord(category=FailureCategory.TOOL, trigger="second"))
        db.record(FailureRecord(category=FailureCategory.COST, trigger="third"))
        triggers = [d["trigger"] for d in db.to_dicts()]
        assert triggers == ["first", "second", "third"]

    def test_as_dict_all_defaults(self):
        rec = FailureRecord(category=FailureCategory.DECISION)
        d = rec.as_dict()
        assert d["context"] == ""
        assert d["trigger"] == ""
        assert d["root_cause"] == ""
        assert d["recovery_action"] == ""
        assert d["final_result"] == ""
        assert d["lesson"] == ""
        assert d["category"] == "decision"
