"""KMA Phase 2 — KnowledgeService Conflict & Supersession Tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore
from nexara_prime.knowledge import KnowledgeService
from nexara_prime.memory import MemoryKernel
from nexara_prime.models import KnowledgeCommit, MemoryKind


@pytest.fixture
def knowledge_service():
    db = Path(tempfile.mkdtemp()) / "test.db"
    store = SQLiteStore(db)
    events = EventBus(store)
    evidence = EvidenceStore(store, events)
    memory = MemoryKernel(store, events, evidence)
    ks = KnowledgeService(memory)
    ks.start()
    return ks


class TestSupersessionDetection:
    def test_new_entry_no_supersession(self, knowledge_service):
        result = knowledge_service.detect_supersession("key1", "content1")
        assert result["action"] == "new"

    def test_duplicate_detection(self, knowledge_service):
        knowledge_service._memory.write(
            MemoryKind.FACT, "dup-key", "same content", "t1",
        )
        result = knowledge_service.detect_supersession("dup-key", "same content")
        assert result["action"] == "duplicate"

    def test_supersedes_canonical(self, knowledge_service):
        knowledge_service._memory.write(
            MemoryKind.FACT, "sup-key", "old content", "t1",
        )
        result = knowledge_service.detect_supersession("sup-key", "new content")
        assert result["action"] == "supersedes"
        assert len(result["supersedes"]) >= 1


class TestConflictDetection:
    def test_no_conflict_for_new_key(self, knowledge_service):
        result = knowledge_service.detect_conflicts("new-key", "content")
        assert result["has_conflicts"] is False

    def test_conflict_detected(self, knowledge_service):
        knowledge_service._memory.write(
            MemoryKind.FACT, "conflict-key", "original", "t1",
        )
        result = knowledge_service.detect_conflicts("conflict-key", "different")
        assert result["has_conflicts"] is True


class TestCommitValidation:
    def test_valid_commit(self, knowledge_service):
        kc = KnowledgeCommit(
            kind=MemoryKind.FACT, key="k", content="c",
            trace_id="t1", idempotency_key="ik-valid",
        )
        result = knowledge_service.validate_commit(kc)
        assert result["valid"] is True

    def test_empty_key_invalid(self, knowledge_service):
        # Pydantic validation catches empty key at construction time
        with pytest.raises(Exception):
            KnowledgeCommit(
                kind=MemoryKind.FACT, key="", content="c",
                trace_id="t1", idempotency_key="ik1",
            )

    def test_missing_trace_id_invalid(self, knowledge_service):
        kc = KnowledgeCommit(
            kind=MemoryKind.FACT, key="k", content="c",
            trace_id="", idempotency_key="ik1",
        )
        result = knowledge_service.validate_commit(kc)
        assert result["valid"] is False

    def test_whitespace_idempotency_key_invalid(self, knowledge_service):
        kc = KnowledgeCommit(
            kind=MemoryKind.FACT, key="k", content="c",
            trace_id="t1", idempotency_key="   ",
        )
        result = knowledge_service.validate_commit(kc)
        assert result["valid"] is False
        assert "idempotency_key_required" in result["errors"]

    def test_unverified_inference_cannot_auto_commit(self, knowledge_service):
        kc = KnowledgeCommit(
            kind=MemoryKind.UNVERIFIED_INFERENCE, key="k", content="c",
            trace_id="t1", auto_commit=True, idempotency_key="ik1",
        )
        result = knowledge_service.validate_commit(kc)
        assert result["valid"] is False

    def test_auto_commit_blocked_by_canonical_conflict(self, knowledge_service):
        # First, write a canonical record
        knowledge_service._memory.write(
            MemoryKind.FACT, "conflict-key", "canonical-content", "t1",
        )
        kc = KnowledgeCommit(
            kind=MemoryKind.FACT, key="conflict-key", content="new-content",
            trace_id="t2", auto_commit=True, idempotency_key="ik-conflict",
        )
        result = knowledge_service.validate_commit(kc)
        assert result["valid"] is False
        assert "auto_commit_blocked_by_canonical_conflict" in result["errors"]


class TestNonSupersededQuery:
    def test_excludes_superseded(self, knowledge_service):
        knowledge_service._memory.write(
            MemoryKind.FACT, "shared-key", "older", "t1",
        )
        knowledge_service._memory.write(
            MemoryKind.FACT, "shared-key", "newer", "t2",
        )
        results = knowledge_service.query_non_superseded()
        assert all(r.get("content") != "older" for r in results)
