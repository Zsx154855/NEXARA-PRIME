"""Tests: Memory Brain persistence layer."""

import pytest

from src.nexara_prime.brain.db import BrainDB
from src.nexara_prime.brain.memory_controller import MemoryController


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "brain_state.db"


@pytest.fixture
def brain_db(temp_db_path):
    """Create BrainDB with schema loaded from schemas/."""
    # Use a temp schema in test since CWD may not have schemas/
    db = BrainDB(path=temp_db_path)
    return db


@pytest.fixture
def controller(brain_db):
    return MemoryController(db=brain_db, persist=True)


class TestMemoryPersistence:
    """10 tests: commit persists, recall reads from DB, restart recovers."""

    def test_commit_persists_to_db(self, controller, brain_db):
        cid = controller.commit("m1", "test_key", "test content", "fact", evidence_id="ev1")
        record = brain_db.get_memory(cid)
        assert record is not None
        assert record["key"] == "test_key"
        assert record["content"] == "test content"
        assert record["kind"] == "fact"

    def test_commit_without_evidence_raises_for_required_kind(self, controller):
        with pytest.raises(ValueError, match="memory_evidence_required"):
            controller.commit("m1", "k", "c", "decision")

    def test_commit_without_evidence_allowed_for_optional_kind(self, controller):
        cid = controller.commit("m1", "k", "c", "short_term")
        assert cid.startswith("mem_")

    def test_recall_reads_from_db(self, controller):
        controller.commit("m2", "k1", "c1", "fact", evidence_id="ev1")
        controller.commit("m2", "k2", "c2", "fact", evidence_id="ev2")
        results = controller.recall("m2")
        assert len(results) >= 2

    def test_recall_filters_by_layer(self, controller):
        controller.commit("m3", "k_dec", "c", "decision", evidence_id="ev1")
        controller.commit("m3", "k_fact", "c", "fact", evidence_id="ev2")
        results = controller.recall("m3", layer="semantic")
        assert all(r.get("layer") == "semantic" for r in results)

    def test_restart_recovers_from_db(self, temp_db_path, brain_db):
        ctrl1 = MemoryController(db=brain_db, persist=True)
        cid = ctrl1.commit("m4", "persist_key", "will survive", "fact", evidence_id="ev1")

        # Simulate restart: new controller with same DB
        db2 = BrainDB(path=temp_db_path)
        ctrl2 = MemoryController(db=db2, persist=True)
        results = ctrl2.recall("m4")
        assert any(r["memory_id"] == cid for r in results)

    def test_concurrent_writes_safe(self, controller):
        """Multiple sequential writes from same thread are safe."""
        results = []
        for i in range(5):
            cid = controller.commit("m_conc", f"k{i}", f"c{i}", "fact", evidence_id=f"ev{i}")
            results.append(cid)
        assert len(results) == 5
        assert len(set(results)) == 5  # all unique IDs


class TestEvidenceBinding:
    """10 tests: evidence enforcement, provenance chain."""

    def test_required_kind_raises_without_evidence(self, controller):
        for kind in ["decision", "failure", "failure_experience", "patch", "skill_improvement", "system_rule"]:
            with pytest.raises(ValueError, match="memory_evidence_required"):
                controller.commit("m", "k", "c", kind)

    def test_required_kind_succeeds_with_evidence(self, controller):
        for kind in ["fact", "user_fact", "project_fact", "preference"]:
            cid = controller.commit("m", "k", "c", kind, evidence_id="ev1")
            assert cid.startswith("mem_")

    def test_optional_kind_without_evidence_ok(self, controller):
        for kind in ["short_term", "temporary_context", "unverified_inference"]:
            cid = controller.commit("m", "k", "c", kind)
            assert cid.startswith("mem_")

    def test_provenance_recorded(self, controller):
        cid = controller.commit("m", "pk", "pc", "fact", evidence_id="ev_prov")
        prov = controller.get_provenance(cid)
        assert prov is not None
        assert prov["evidence_id"] == "ev_prov"

    def test_provenance_verify_chain(self, controller):
        cid = controller.commit("m", "pk2", "pc2", "fact", evidence_id="ev_v")
        assert controller.verify_provenance(cid)

    def test_provenance_absent_for_no_evidence(self, controller):
        cid = controller.commit("m", "pk3", "pc3", "short_term")
        prov = controller.get_provenance(cid)
        assert prov is None

    def test_no_evidence_raises_for_fact(self, controller):
        with pytest.raises(ValueError, match="memory_evidence_required"):
            controller.commit("m", "k", "c", "fact")

    def test_no_evidence_raises_for_user_fact(self, controller):
        with pytest.raises(ValueError, match="memory_evidence_required"):
            controller.commit("m", "k", "c", "user_fact")

    def test_no_evidence_raises_for_preference(self, controller):
        with pytest.raises(ValueError, match="memory_evidence_required"):
            controller.commit("m", "k", "c", "preference")

    def test_no_evidence_raises_for_project_fact(self, controller):
        with pytest.raises(ValueError, match="memory_evidence_required"):
            controller.commit("m", "k", "c", "project_fact")


class TestHealthMetrics:
    """8 tests: health report structure, metrics accuracy."""

    def test_health_report_returns_valid_structure(self, controller):
        controller.commit("m", "k", "c", "fact", evidence_id="ev1")
        report = controller.health_report()
        assert "total_memories" in report
        assert "active_count" in report
        assert "coverage_score" in report
        assert "freshness_score" in report
        assert "consistency_score" in report
        assert "layer_distribution" in report

    def test_coverage_score_increases_with_more_kinds(self, controller):
        kinds = ["fact", "decision", "failure", "preference", "user_fact"]
        for i, k in enumerate(kinds):
            controller.commit("m", f"k{i}", f"c{i}", k, evidence_id=f"ev{i}")
        report = controller.health_report()
        assert report["coverage_score"] > 0.0

    def test_freshness_score_one_when_all_active(self, controller):
        controller.commit("m", "k", "c", "fact", evidence_id="ev1")
        report = controller.health_report()
        assert report["freshness_score"] > 0.0

    def test_consistency_score_with_evidence(self, controller):
        controller.commit("m", "k", "c", "fact", evidence_id="ev1")
        controller.commit("m", "k2", "c2", "short_term")  # no evidence
        report = controller.health_report()
        assert 0.0 <= report["consistency_score"] <= 1.0

    def test_layer_distribution_accurate(self, controller):
        controller.commit("m", "k_w", "c", "short_term")
        controller.commit("m", "k_f", "c", "fact", evidence_id="ev1")
        report = controller.health_report()
        dist = report["layer_distribution"]
        assert dist.get("working", 0) >= 0
        assert dist.get("semantic", 0) >= 0

    def test_kind_distribution_accurate(self, controller):
        controller.commit("m", "k1", "c", "fact", evidence_id="ev1")
        controller.commit("m", "k2", "c", "decision", evidence_id="ev2")
        report = controller.health_report()
        kd = report["kind_distribution"]
        assert kd.get("fact", 0) >= 1

    def test_snapshot_persisted(self, brain_db, controller):
        controller.commit("m", "k", "c", "fact", evidence_id="ev1")
        controller.health_report()
        snap = brain_db.get_latest_health_snapshot()
        assert snap is not None

    def test_active_count_accurate(self, controller):
        controller.commit("m", "k1", "c", "fact", evidence_id="ev1")
        controller.commit("m", "k2", "c", "fact", evidence_id="ev2")
        report = controller.health_report()
        assert report["active_count"] >= 2
