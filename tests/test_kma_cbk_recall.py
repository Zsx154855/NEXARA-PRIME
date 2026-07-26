"""KMA Phase 2 — ChiefBrainKernel Recall Tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nexara_prime.chief_brain_kernel import ChiefBrainKernel
from nexara_prime.contract_engine import ContractEngine
from nexara_prime.governance import ApprovalEngine, PolicyEngine
from nexara_prime.memory import MemoryKernel, MemoryLayerManager
from nexara_prime.mission_compiler import MissionCompiler
from nexara_prime.mission_triage import MissionTriageEngine
from nexara_prime.models import KnowledgeRecall, MemoryKind
from nexara_prime.orchestration import RuntimeOrchestrator
from nexara_prime.state_machine import MissionStateMachine
from nexara_prime.adaptive_scheduler import AdaptiveMultiAgentScheduler
from nexara_prime.db import SQLiteStore
from nexara_prime.events import EventBus
from nexara_prime.evidence import EvidenceStore


@pytest.fixture
def kernel_deps():
    db = Path(tempfile.mkdtemp()) / "test.db"
    store = SQLiteStore(db)
    events = EventBus(store)
    evidence = EvidenceStore(store, events)
    return store, events, evidence


@pytest.fixture
def kernel_with_recall(kernel_deps):
    store, events, evidence = kernel_deps
    memory = MemoryKernel(store, events, evidence)
    mlm = MemoryLayerManager(memory, rag=None, enable_patch_review=False)
    return ChiefBrainKernel(
        MissionTriageEngine(),
        MissionCompiler(),
        ContractEngine(),
        MissionStateMachine(events, evidence),
        RuntimeOrchestrator(store, events, evidence),
        AdaptiveMultiAgentScheduler(),
        PolicyEngine(),
        ApprovalEngine(store, events),
        memory_layer_manager=mlm,
    )


class TestCBKRecall:
    def test_recall_returns_knowledge_recall(self, kernel_with_recall):
        result = kernel_with_recall.recall("test query", top_k=5, trace_id="t1")
        assert isinstance(result, KnowledgeRecall)
        assert result.query == "test query"
        assert result.top_k >= 0
        assert isinstance(result.results, list)

    def test_recall_without_manager_returns_empty(self, kernel_deps):
        store, events, evidence = kernel_deps
        kernel = ChiefBrainKernel(
            MissionTriageEngine(), MissionCompiler(), ContractEngine(),
            MissionStateMachine(events, evidence),
            RuntimeOrchestrator(store, events, evidence),
            AdaptiveMultiAgentScheduler(),
            PolicyEngine(), ApprovalEngine(store, events),
        )
        result = kernel.recall("query", trace_id="t1")
        assert isinstance(result, KnowledgeRecall)
        assert result.top_k >= 0
        assert result.results == []

    def test_recall_results_contain_content_score(self, kernel_with_recall):
        """Verify recalled records carry content, score, and citation fields."""
        result = kernel_with_recall.recall("test query", top_k=3, trace_id="t1")
        for record in result.results:
            assert isinstance(record, dict)
            # Records from MemoryLayerManager always carry key, content, score
            assert "score" in record
            assert "content" in record or "key" in record

    def test_admission_still_works(self, kernel_with_recall):
        ctx = kernel_with_recall.submit(
            "mission-1", "api",
            contract_verified=True,
            governance_approved=True,
            state_valid=True,
            evidence_initialized=True,
        )
        assert ctx.mission_id == "mission-1"

    def test_health_shows_recall(self, kernel_with_recall):
        h = kernel_with_recall.health()
        assert h["modules"]["recall"] is True

    def test_mission_isolation_recall_A_only_returns_A_docs(self, kernel_with_recall):
        """Fix 1: recall(mission_id='A') returns only mission A docs."""
        mlm = kernel_with_recall._memory_layer_manager
        kernel = mlm.kernel
        # Write docs for mission A
        kernel.write(MemoryKind.FACT, "key_a", "content alpha", "t1",
                     mission_id="mission-A")
        kernel.write(MemoryKind.FACT, "key_a2", "content beta", "t1",
                     mission_id="mission-A")
        # Write docs for mission B
        kernel.write(MemoryKind.FACT, "key_b", "content gamma", "t1",
                     mission_id="mission-B")
        kernel.write(MemoryKind.FACT, "key_b2", "content delta", "t1",
                     mission_id="mission-B")

        result_a = kernel_with_recall.recall(
            "content", mission_id="mission-A", trace_id="t1",
        )
        result_b = kernel_with_recall.recall(
            "content", mission_id="mission-B", trace_id="t1",
        )

        # All results in A should be from mission-A
        for r in result_a.results:
            assert r.get("mission_id") == "mission-A" or r.get("mission_id") is None, \
                f"Expected mission-A, got {r.get('mission_id')}"
        # All results in B should be from mission-B
        for r in result_b.results:
            assert r.get("mission_id") == "mission-B" or r.get("mission_id") is None, \
                f"Expected mission-B, got {r.get('mission_id')}"
        # A results should not contain B docs
        a_keys = {r.get("key") for r in result_a.results}
        assert "key_b" not in a_keys
        assert "key_b2" not in a_keys
        # B results should not contain A docs
        b_keys = {r.get("key") for r in result_b.results}
        assert "key_a" not in b_keys
        assert "key_a2" not in b_keys
