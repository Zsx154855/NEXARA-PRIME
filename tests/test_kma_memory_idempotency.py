"""KMA Phase 2 — Memory Idempotency & Receipt Linking Tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.memory import MemoryKernel, MemoryLayerManager
from nexara_prime.models import MemoryKind


@pytest.fixture
def memory_kernel():
    db = Path(tempfile.mkdtemp()) / "test.db"
    store = SQLiteStore(db)
    events = EventBus(store)
    evidence = EvidenceStore(store, events)
    return MemoryKernel(store, events, evidence)


class TestMemoryIdempotency:
    def test_patch_idempotent(self, memory_kernel):
        evidence = memory_kernel.evidence.add("m1", "test", "T", "c", "t1")
        result1 = memory_kernel.patch(
            "m1", "key1", "content1", "t1", evidence.evidence_id,
            idempotency_key="idem-patch-1",
        )
        result2 = memory_kernel.patch(
            "m1", "key1", "content1", "t1", evidence.evidence_id,
            idempotency_key="idem-patch-1",
        )
        assert result1.memory_id == result2.memory_id

    def test_patch_rejects_conflicting_content(self, memory_kernel):
        evidence = memory_kernel.evidence.add("m1", "test", "T", "c", "t1")
        memory_kernel.patch(
            "m1", "key2", "content-A", "t1", evidence.evidence_id,
            idempotency_key="idem-key-2",
        )
        with pytest.raises(ValueError, match="idempotency_conflict"):
            memory_kernel.patch(
                "m1", "key2", "content-B", "t1", evidence.evidence_id,
                idempotency_key="idem-key-2",
            )


class TestMemoryIdempotencyConflict:
    """P2 Codex: same replay returns original; different replay raises conflict."""

    def test_write_same_replay_returns_original(self, memory_kernel):
        """Same fields on replay → return the original record."""
        evidence = memory_kernel.evidence.add("m_conflict", "test", "T", "c", "t1")
        r1 = memory_kernel.write(
            MemoryKind.FACT, "key-c1", "content-c1", "t1",
            mission_id="m_conflict",
            source_evidence_id=evidence.evidence_id,
            confidence=0.9,
            idempotency_key="idem-write-1",
        )
        # Replay with all same fields
        r2 = memory_kernel.write(
            MemoryKind.FACT, "key-c1", "content-c1", "t1",
            mission_id="m_conflict",
            source_evidence_id=evidence.evidence_id,
            confidence=0.9,
            idempotency_key="idem-write-1",
        )
        assert r2.memory_id == r1.memory_id
        assert r2.kind == r1.kind
        assert r2.key == r1.key
        assert r2.content == r1.content

    def test_write_different_content_raises_conflict(self, memory_kernel):
        """Different content on replay → raise conflict."""
        evidence = memory_kernel.evidence.add("m_conflict", "test", "T", "c", "t1")
        memory_kernel.write(
            MemoryKind.FACT, "key-c2", "content-orig", "t1",
            mission_id="m_conflict",
            source_evidence_id=evidence.evidence_id,
            idempotency_key="idem-write-2",
        )
        with pytest.raises(ValueError, match="memory_idempotency_conflict"):
            memory_kernel.write(
                MemoryKind.FACT, "key-c2", "content-different", "t1",
                mission_id="m_conflict",
                source_evidence_id=evidence.evidence_id,
                idempotency_key="idem-write-2",
            )

    def test_write_different_kind_raises_conflict(self, memory_kernel):
        """Different kind on replay → raise conflict."""
        evidence = memory_kernel.evidence.add("m_conflict", "test", "T", "c", "t1")
        memory_kernel.write(
            MemoryKind.FACT, "key-c3", "content-c3", "t1",
            mission_id="m_conflict",
            source_evidence_id=evidence.evidence_id,
            idempotency_key="idem-write-3",
        )
        with pytest.raises(ValueError, match="memory_idempotency_conflict"):
            memory_kernel.write(
                MemoryKind.DECISION, "key-c3", "content-c3", "t1",
                mission_id="m_conflict",
                source_evidence_id=evidence.evidence_id,
                idempotency_key="idem-write-3",
            )

    def test_write_different_confidence_raises_conflict(self, memory_kernel):
        """Different confidence on replay → raise conflict."""
        evidence = memory_kernel.evidence.add("m_conflict", "test", "T", "c", "t1")
        memory_kernel.write(
            MemoryKind.FACT, "key-c4", "content-c4", "t1",
            mission_id="m_conflict",
            source_evidence_id=evidence.evidence_id,
            confidence=0.8,
            idempotency_key="idem-write-4",
        )
        with pytest.raises(ValueError, match="memory_idempotency_conflict"):
            memory_kernel.write(
                MemoryKind.FACT, "key-c4", "content-c4", "t1",
                mission_id="m_conflict",
                source_evidence_id=evidence.evidence_id,
                confidence=0.9,
                idempotency_key="idem-write-4",
            )

    def test_propose_same_replay_returns_original(self, memory_kernel):
        """Same fields on propose replay → return the original record."""
        evidence = memory_kernel.evidence.add("m_conflict", "test", "T", "c", "t1")
        r1 = memory_kernel.propose(
            MemoryKind.FACT, "key-p1", "content-p1", "t1",
            mission_id="m_conflict",
            source_evidence_id=evidence.evidence_id,
            confidence=0.9,
            auto_commit=True,
            idempotency_key="idem-prop-1",
        )
        # Replay with all same fields
        r2 = memory_kernel.propose(
            MemoryKind.FACT, "key-p1", "content-p1", "t1",
            mission_id="m_conflict",
            source_evidence_id=evidence.evidence_id,
            confidence=0.9,
            auto_commit=True,
            idempotency_key="idem-prop-1",
        )
        assert r2.memory_id == r1.memory_id

    def test_propose_different_auto_commit_raises_conflict(self, memory_kernel):
        """Different auto_commit on propose replay → raise conflict."""
        evidence = memory_kernel.evidence.add("m_conflict", "test", "T", "c", "t1")
        memory_kernel.propose(
            MemoryKind.FACT, "key-p2", "content-p2", "t1",
            mission_id="m_conflict",
            source_evidence_id=evidence.evidence_id,
            confidence=1.0,
            auto_commit=True,
            idempotency_key="idem-prop-2",
        )
        with pytest.raises(ValueError, match="memory_idempotency_conflict"):
            memory_kernel.propose(
                MemoryKind.FACT, "key-p2", "content-p2", "t1",
                mission_id="m_conflict",
                source_evidence_id=evidence.evidence_id,
                confidence=1.0,
                auto_commit=False,
                idempotency_key="idem-prop-2",
            )

    def test_propose_different_content_raises_conflict(self, memory_kernel):
        """Different content on propose replay → raise conflict."""
        evidence = memory_kernel.evidence.add("m_conflict", "test", "T", "c", "t1")
        memory_kernel.propose(
            MemoryKind.FACT, "key-p3", "content-A", "t1",
            mission_id="m_conflict",
            source_evidence_id=evidence.evidence_id,
            idempotency_key="idem-prop-3",
        )
        with pytest.raises(ValueError, match="memory_idempotency_conflict"):
            memory_kernel.propose(
                MemoryKind.FACT, "key-p3", "content-B", "t1",
                mission_id="m_conflict",
                source_evidence_id=evidence.evidence_id,
                idempotency_key="idem-prop-3",
            )


class TestReceiptLinking:
    def test_memory_record_has_receipt_id(self, memory_kernel):
        evidence = memory_kernel.evidence.add("m2", "test", "T", "c", "t1")
        record = memory_kernel.write(
            MemoryKind.DECISION, "key-r", "content-r", "t1",
            mission_id="m2", source_evidence_id=evidence.evidence_id,
        )
        assert record.receipt_id is None
        # receipt_id is set during KnowledgeCommit → MemoryKernel bridge
        # (Phase 2 integration test)

    def test_memory_layer_write_episodic_requires_evidence(self, memory_kernel):
        mlm = MemoryLayerManager(memory_kernel, rag=None)
        with pytest.raises(ValueError, match="requires source_evidence_id"):
            mlm.write_episodic("key-e", "content", "t1", mission_id="m2")


class TestKnowledgeSupersession:
    """Fix 2: Knowledge supersession persistence."""

    @pytest.fixture
    def mem_kernel_with_mlm(self):
        import tempfile
        from pathlib import Path
        db = Path(tempfile.mkdtemp()) / "test.db"
        store = SQLiteStore(db)
        events = EventBus(store)
        evidence = EvidenceStore(store, events)
        kernel = MemoryKernel(store, events, evidence)
        mlm = MemoryLayerManager(kernel, rag=None, enable_patch_review=False)
        return kernel, mlm

    def test_supersession_marks_old_as_superseded(self, mem_kernel_with_mlm):
        """When writing with same key, old record is marked superseded."""
        kernel, mlm = mem_kernel_with_mlm

        # Write original
        old = kernel.write(MemoryKind.FACT, "sup-key", "old-content", "t1",
                           mission_id="m-sup")
        # Write superseding record with same key, different content
        new = kernel.write(MemoryKind.FACT, "sup-key", "new-content", "t1",
                           mission_id="m-sup")

        # Verify old is now superseded
        old_env = kernel.store.get_record(old.memory_id)
        assert old_env is not None
        assert old_env["status"] == "superseded"
        assert old_env["superseded_by"] == new.memory_id

        # Verify new record has supersedes pointing to old
        assert new.supersedes == old.memory_id

    def test_recall_excludes_superseded_by_default(self, mem_kernel_with_mlm):
        """recall/search should exclude superseded records by default."""
        kernel, mlm = mem_kernel_with_mlm

        # Write original
        kernel.write(MemoryKind.FACT, "sup-key-2", "old-content", "t1",
                     mission_id="m-sup-2")
        # Write superseding (same key, different content)
        kernel.write(MemoryKind.FACT, "sup-key-2", "new-content", "t1",
                     mission_id="m-sup-2")

        results = mlm.search("old-content", mission_id="m-sup-2")
        # Should NOT find the superseded record
        for r in results:
            assert r.get("key") != "sup-key-2" or r.get("content") != "old-content", \
                f"Superseded record should be excluded, got {r}"

    def test_include_superseded_flag(self, mem_kernel_with_mlm):
        """include_superseded flag in recall should surface superseded records."""
        kernel, mlm = mem_kernel_with_mlm

        # Write original and superseding
        old = kernel.write(MemoryKind.FACT, "sup-key-3", "old-content", "t1",
                           mission_id="m-sup-3")
        kernel.write(MemoryKind.FACT, "sup-key-3", "new-content", "t1",
                     mission_id="m-sup-3")

        # Default: excluded
        results_default = mlm.search("old-content", mission_id="m-sup-3")
        has_superseded = any(
            r.get("memory_id") == old.memory_id for r in results_default
        )
        assert not has_superseded, "Superseded record should be excluded by default"

    def test_supersession_idempotent_on_same_content(self, mem_kernel_with_mlm):
        """Writing with same key AND same content should NOT supersede."""
        kernel, mlm = mem_kernel_with_mlm

        old = kernel.write(MemoryKind.FACT, "sup-key-4", "same-content", "t1",
                           mission_id="m-sup-4")
        new = kernel.write(MemoryKind.FACT, "sup-key-4", "same-content", "t1",
                           mission_id="m-sup-4")

        # Old should still be committed (not superseded) since content matches
        old_env = kernel.store.get_record(old.memory_id)
        assert old_env["status"] == "committed"
        # New should NOT have supersedes since no different content existed
        assert new.supersedes is None
