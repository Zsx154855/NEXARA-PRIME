"""Tests: Evidence binding for brain memory operations."""

import pytest
from src.nexara_prime.brain.db import BrainDB
from src.nexara_prime.brain.memory_controller import MemoryController, EVIDENCE_REQUIRED_KINDS, EVIDENCE_OPTIONAL_KINDS


@pytest.fixture
def controller(tmp_path):
    db = BrainDB(path=tmp_path / "brain_state.db")
    return MemoryController(db=db, persist=True)


class TestEvidenceBindingEnforcement:
    """10 tests: required kinds raise, optional kinds pass, provenance."""

    def test_all_required_kinds_raise_without_evidence(self, controller):
        for kind in EVIDENCE_REQUIRED_KINDS:
            with pytest.raises(ValueError, match="memory_evidence_required"):
                controller.commit("m", "k", "c", kind)

    def test_all_required_kinds_succeed_with_evidence(self, controller):
        for i, kind in enumerate(sorted(EVIDENCE_REQUIRED_KINDS)):
            cid = controller.commit("m", f"k{i}", f"c{i}", kind, evidence_id=f"ev_{i}")
            assert cid.startswith("mem_")

    def test_all_optional_kinds_succeed_without_evidence(self, controller):
        for kind in EVIDENCE_OPTIONAL_KINDS:
            cid = controller.commit("m", "k", "c", kind)
            assert cid.startswith("mem_")

    def test_provenance_starts_at_evidence(self, controller):
        cid = controller.commit("m", "k", "c", "fact", evidence_id="ev_start")
        prov = controller.get_provenance(cid)
        assert prov is not None
        assert prov["evidence_id"] == "ev_start"
        assert prov["memory_id"] == cid

    def test_get_provenance_returns_full_chain(self, controller):
        cid = controller.commit("m", "k", "c", "fact", evidence_id="ev_chain",
                               provenance_source_file="test.py",
                               provenance_commit_sha="abc123")
        prov = controller.get_provenance(cid)
        assert prov is not None
        assert prov.get("source_file") == "test.py"
        assert prov.get("commit_sha") == "abc123"

    def test_verify_chain_detects_valid_chain(self, controller):
        cid = controller.commit("m", "k", "c", "fact", evidence_id="ev_valid")
        assert controller.verify_provenance(cid)

    def test_verify_chain_rejects_missing(self, controller):
        assert not controller.verify_provenance("nonexistent_id")

    def test_provenance_chain_hash_computable(self, controller):
        from src.nexara_prime.brain.provenance import ProvenanceTracker
        cid = controller.commit("m", "k", "c", "fact", evidence_id="ev_hash")
        tracker = ProvenanceTracker(controller._db)
        hash_val = tracker.compute_chain_hash(cid)
        assert hash_val is not None
        assert len(hash_val) == 64  # SHA-256 hex length

    def test_evidence_optional_no_provenance(self, controller):
        cid = controller.commit("m", "k", "c", "short_term")
        prov = controller.get_provenance(cid)
        assert prov is None

    def test_multiple_evidence_bound_commits(self, controller):
        ids = []
        for i in range(5):
            cid = controller.commit("m", f"k{i}", f"c{i}", "fact", evidence_id=f"ev_{i}")
            ids.append(cid)
        for cid in ids:
            prov = controller.get_provenance(cid)
            assert prov is not None


class TestExpandedEvidenceBinding:
    """Verify the expansion from 6 to 10 required kinds."""

    def test_expanded_kinds_include_fact_types(self):
        """fact, user_fact, project_fact, preference are now required."""
        assert "fact" in EVIDENCE_REQUIRED_KINDS
        assert "user_fact" in EVIDENCE_REQUIRED_KINDS
        assert "project_fact" in EVIDENCE_REQUIRED_KINDS
        assert "preference" in EVIDENCE_REQUIRED_KINDS

    def test_original_6_still_required(self):
        original = {"decision", "failure", "failure_experience", "patch", "skill_improvement", "system_rule"}
        assert original.issubset(EVIDENCE_REQUIRED_KINDS)

    def test_optional_kinds_unchanged(self):
        optional = {"short_term", "temporary_context", "unverified_inference"}
        assert optional == EVIDENCE_OPTIONAL_KINDS

    def test_total_covered_kinds(self):
        """All 13 MemoryKind values should be covered by required + optional."""
        from src.nexara_prime.models import MemoryKind
        all_kinds = {k.value for k in MemoryKind}
        covered = EVIDENCE_REQUIRED_KINDS | EVIDENCE_OPTIONAL_KINDS
        assert all_kinds == covered, f"Missing: {all_kinds - covered}"
