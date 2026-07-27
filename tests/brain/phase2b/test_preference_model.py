"""Tests: Personal Preference Model."""
import pytest
from src.nexara_prime.brain.preference_model import PreferenceModel


@pytest.fixture
def mc(mock_mc):
    return mock_mc


@pytest.fixture
def model(mc):
    return PreferenceModel(mc)


class TestPreferenceCRUD:
    def test_record_new_preference(self, model):
        cid = model.record_preference("m1", "theme", "visual", "dark")
        assert cid is not None

    def test_get_preference_returns_entity(self, model):
        model.record_preference("m1", "lang", "language", "zh")
        pref = model.get_preference("m1", "lang")
        assert pref is not None
        assert pref.key == "lang"

    def test_get_nonexistent_returns_none(self, model):
        assert model.get_preference("m1", "nonexistent") is None

    def test_get_all_preferences(self, model):
        model.record_preference("m1", "a", "visual", "dark")
        model.record_preference("m1", "b", "language", "zh")
        prefs = model.get_all_preferences("m1")
        assert len(prefs) == 2

    def test_update_overwrites(self, model):
        model.record_preference("m1", "theme", "visual", "dark", weight=0.5)
        model.record_preference("m1", "theme", "visual", "light", weight=0.9)
        pref = model.get_preference("m1", "theme")
        assert pref.value == "light"


class TestPreferenceRanking:
    def test_rank_returns_preferences(self, model):
        model.record_preference("m1", "a", "visual", "dark", weight=0.3, confidence=0.5)
        model.record_preference("m1", "b", "visual", "light", weight=0.9, confidence=0.9)
        ranked = model.rank_preferences("visual theme", top_k=5)
        assert len(ranked) >= 1

    def test_rank_respects_top_k(self, model):
        for i in range(5):
            model.record_preference("m1", f"k{i}", "test", f"v{i}")
        ranked = model.rank_preferences("test", top_k=3)
        assert len(ranked) <= 3


class TestDecay:
    def test_decay_reduces_weights(self, model):
        model.record_preference("global", "old_pref", "test", "val", weight=1.0, confidence=1.0)
        decayed = model.apply_decay("global", half_life_hours=1)
        assert decayed >= 1
        pref = model.get_preference("global", "old_pref")
        assert pref is not None
        assert pref.weight < 1.0


class TestConflictResolution:
    def test_no_existing_creates_new(self, model):
        cid = model.resolve_conflict("m1", "new_pref", "value_b", confidence=0.8, evidence_id="ev1")
        assert cid is not None

    def test_higher_confidence_wins(self, model):
        model.record_preference("m1", "conflict", "test", "old_val", weight=0.3, confidence=0.3)
        model.resolve_conflict("m1", "conflict", "new_val", confidence=0.9, evidence_id="ev2")
        pref = model.get_preference("m1", "conflict")
        assert pref.value == "new_val"

    def test_evidence_backed_overrides(self, model):
        model.record_preference("m1", "ev_pref", "test", "weak", weight=0.9, confidence=0.9)
        model.resolve_conflict("m1", "ev_pref", "strong", evidence_id="ev_strong", confidence=0.1)
        pref = model.get_preference("m1", "ev_pref")
        assert pref.value == "strong"


class TestProfile:
    def test_get_profile(self, model):
        model.record_preference("global", "a", "visual", "dark")
        model.record_preference("global", "b", "language", "zh")
        p = model.get_profile()
        assert p["total_preferences"] >= 2

    def test_summarize(self, model):
        model.record_preference("global", "x", "test", "y")
        s = model.summarize()
        assert "total_preferences" in s
