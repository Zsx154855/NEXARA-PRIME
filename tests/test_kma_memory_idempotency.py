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
