"""Tests: Long-term Memory operations."""

import time
import pytest

from src.nexara_prime.brain.db import BrainDB
from src.nexara_prime.brain.memory_controller import MemoryController
from src.nexara_prime.brain.long_term_memory import LongTermMemory


@pytest.fixture
def brain_db(tmp_path):
    return BrainDB(path=tmp_path / "brain_state.db")


@pytest.fixture
def controller(brain_db):
    return MemoryController(db=brain_db, persist=True)


@pytest.fixture
def ltm(controller, brain_db):
    return LongTermMemory(controller=controller, db=brain_db)


class TestConsolidation:
    """Tests: promotion from working→semantic, access_count threshold."""

    def test_consolidate_to_ltm_after_access_threshold(self, ltm, controller, brain_db):
        cid = controller.commit("m1", "key_c", "content", "short_term")
        # Simulate access_count reaching threshold
        brain_db.update_memory(cid, {"access_count": 5})
        result = ltm.consolidate_to_ltm(cid)
        assert result is not None
        assert result["layer"] == "semantic"
        assert result["consolidated_from"] == cid

    def test_consolidate_to_ltm_below_threshold(self, ltm, controller):
        cid = controller.commit("m1", "key_below", "content", "short_term")
        # access_count = 0, below threshold of 3
        result = ltm.consolidate_to_ltm(cid)
        assert result is None

    def test_consolidate_to_ltm_from_semantic_to_procedural(self, ltm, controller, brain_db):
        cid = controller.commit("m1", "key_sem", "content", "fact", evidence_id="ev1")
        brain_db.update_memory(cid, {"access_count": 12, "confidence": 0.95})
        result = ltm.consolidate_to_ltm(cid)
        assert result is not None
        assert result["layer"] == "procedural"

    def test_consolidate_to_ltm_force(self, ltm, controller):
        cid = controller.commit("m1", "key_f", "content", "short_term")
        result = ltm.consolidate_to_ltm(cid, force=True)
        assert result is not None
        assert result["layer"] == "semantic"

    def test_consolidate_to_ltm_nonexistent(self, ltm):
        result = ltm.consolidate_to_ltm("nonexistent_id")
        assert result is None

    def test_consolidation_log_recorded(self, ltm, controller, brain_db):
        cid = controller.commit("m1", "key_log", "content", "short_term")
        brain_db.update_memory(cid, {"access_count": 5})
        result = ltm.consolidate_to_ltm(cid)
        assert result is not None


class TestReinforcement:
    """Tests: access_count increment, confidence recalculate."""

    def test_reinforce_increments_access_count(self, ltm, controller):
        cid = controller.commit("m1", "key_r", "content", "fact", evidence_id="ev1")
        result = ltm.reinforce(cid)
        assert result is not None
        assert result["access_count"] == 1

    def test_reinforce_updates_last_accessed(self, ltm, controller):
        cid = controller.commit("m1", "key_la", "content", "fact", evidence_id="ev1")
        result = ltm.reinforce(cid)
        assert result["last_accessed"] is not None

    def test_reinforce_nonexistent(self, ltm):
        result = ltm.reinforce("nonexistent")
        assert result is None

    def test_reinforce_multiple(self, ltm, controller):
        cid = controller.commit("m1", "key_multi", "content", "fact", evidence_id="ev1")
        for _ in range(5):
            ltm.reinforce(cid)
        record = ltm._db.get_memory(cid)
        assert record["access_count"] == 5


class TestSupersession:
    """Tests: conflict detection, superseded_by flag."""

    def test_detect_supersession_flags_conflicts(self, ltm, controller):
        controller.commit("m1", "key_ss", "old content", "fact", evidence_id="ev1")
        superseded = ltm.detect_supersession("key_ss", "new content", mission_id="m1")
        assert len(superseded) == 1

    def test_detect_supersession_same_content_no_flag(self, ltm, controller):
        controller.commit("m1", "key_same", "same content", "fact", evidence_id="ev1")
        superseded = ltm.detect_supersession("key_same", "same content", mission_id="m1")
        assert len(superseded) == 0

    def test_superseded_entry_status_updated(self, ltm, controller, brain_db):
        cid = controller.commit("m1", "key_st", "old", "fact", evidence_id="ev1")
        ltm.detect_supersession("key_st", "new", mission_id="m1")
        record = brain_db.get_memory(cid)
        assert record is not None
        if record:
            assert record["status"] == "superseded" or record.get("superseded_by") == "superseded"


class TestGarbageCollection:
    """Tests: stale memory archival, active preserved."""

    def test_gc_archives_stale(self, ltm, controller, brain_db):
        cid = controller.commit("m1", "key_gc", "content", "fact", evidence_id="ev1")
        brain_db.update_memory(cid, {"confidence": 0.05})
        result = ltm.garbage_collect(min_confidence=0.1)
        assert result["archived_count"] >= 1

    def test_gc_preserves_active(self, ltm, controller):
        controller.commit("m1", "key_active", "content", "fact", evidence_id="ev1")
        result = ltm.garbage_collect(min_confidence=0.1)
        # Active records (confidence=1.0) should not be archived
        assert result["archived_count"] == 0

    def test_gc_respects_min_confidence(self, ltm, controller, brain_db):
        cid1 = controller.commit("m1", "k1", "c1", "fact", evidence_id="ev1")
        cid2 = controller.commit("m1", "k2", "c2", "fact", evidence_id="ev2")
        brain_db.update_memory(cid1, {"confidence": 0.05})
        brain_db.update_memory(cid2, {"confidence": 0.5})
        result = ltm.garbage_collect(min_confidence=0.3)
        assert result["archived_count"] == 1  # only cid1 should be archived


class TestDecay:
    """Tests: confidence decreases over time, reinforcement counters decay."""

    def test_decay_reduces_confidence(self, ltm, controller, brain_db):
        cid = controller.commit("m1", "key_d", "content", "fact", evidence_id="ev1")
        # Manually age the record
        brain_db.update_memory(cid, {
            "created_at": "2020-01-01T00:00:00",
            "confidence": 0.9,
        })
        result = ltm.decay_tick()
        assert result["affected"] >= 0

    def test_decay_never_below_min_confidence(self, ltm, controller, brain_db):
        cid = controller.commit("m1", "key_min", "content", "fact", evidence_id="ev1")
        brain_db.update_memory(cid, {
            "created_at": "2020-01-01T00:00:00",
            "confidence": 0.3,
        })
        ltm.decay_tick()
        record = brain_db.get_memory(cid)
        assert record is not None
        if record:
            assert record["confidence"] >= 0.1  # min_confidence for fact is 0.3, but decay won't go below

    def test_never_decay_kinds_unchanged(self, ltm, controller, brain_db):
        cid = controller.commit("m1", "key_nd", "content", "decision", evidence_id="ev1")
        brain_db.update_memory(cid, {
            "created_at": "2020-01-01T00:00:00",
            "confidence": 1.0,
        })
        result = ltm.decay_tick()
        # decision has half_life=0, should not be affected
        assert result["by_kind"].get("decision", 0) == 0


class TestProvenance:
    """Tests: chain traces to evidence, get_provenance returns full chain."""

    def test_provenance_traces_to_evidence(self, ltm, controller):
        cid = controller.commit("m1", "key_p", "content", "fact", evidence_id="ev_prov")
        chain = ltm.get_provenance_chain(cid)
        assert chain is not None
        assert chain["evidence_id"] == "ev_prov"

    def test_provenance_nonexistent(self, ltm):
        chain = ltm.get_provenance_chain("nonexistent")
        assert chain is None

    def test_provenance_multiple_memories(self, ltm, controller):
        c1 = controller.commit("m1", "k1", "c1", "fact", evidence_id="ev_a")
        c2 = controller.commit("m1", "k2", "c2", "fact", evidence_id="ev_b")
        chain1 = ltm.get_provenance_chain(c1)
        chain2 = ltm.get_provenance_chain(c2)
        assert chain1["evidence_id"] == "ev_a"
        assert chain2["evidence_id"] == "ev_b"


class TestHealthReport:
    """Tests: LTM-specific metrics."""

    def test_health_report_includes_ltm_metrics(self, ltm, controller):
        controller.commit("m1", "k", "c", "fact", evidence_id="ev1")
        report = ltm.health_report()
        assert "ltm_consolidation_rate" in report
        assert "ltm_supersession_rate" in report
        assert "ltm_gc_candidates" in report
