"""Tests: Context Assembly — 6-step pipeline, bounding, MemoryRetrievalAdapter."""

import pytest
from src.nexara_prime.brain.reasoning import (
    ContextAssembler, MemoryRetrievalAdapter,
    MissionContext, AssembledContext,
)


@pytest.fixture
def adapter():
    return MemoryRetrievalAdapter(memory=None)


@pytest.fixture
def assembler(adapter):
    return ContextAssembler(adapter)


@pytest.fixture
def mission():
    return MissionContext(
        mission_id="m1",
        objective="Generate a report on system performance",
        risk_level="R1",
        constraints=["Local only", "Read-only"],
    )


class TestContextAssembly:
    """15 tests: pipeline, bounding, memory retrieval."""

    def test_assemble_returns_context(self, assembler, mission):
        ctx = assembler.assemble(mission)
        assert isinstance(ctx, AssembledContext)

    def test_assemble_has_mission_summary(self, assembler, mission):
        ctx = assembler.assemble(mission)
        assert mission.objective in ctx.mission_summary

    def test_assemble_respects_max_items(self, assembler, mission):
        ctx = assembler.assemble(mission)
        assert ctx.max_items == 50

    def test_assemble_respects_max_tokens(self, assembler, mission):
        ctx = assembler.assemble(mission)
        assert ctx.max_tokens == 5000

    def test_assemble_context_size_within_bounds(self, assembler, mission):
        ctx = assembler.assemble(mission)
        assert ctx.context_size <= 5000

    def test_empty_mission_produces_context(self, assembler):
        empty = MissionContext(mission_id="m_empty")
        ctx = assembler.assemble(empty)
        assert isinstance(ctx, AssembledContext)

    def test_relevant_memories_is_list(self, assembler, mission):
        ctx = assembler.assemble(mission)
        assert isinstance(ctx.relevant_memories, list)

    def test_past_decisions_is_list(self, assembler, mission):
        ctx = assembler.assemble(mission)
        assert isinstance(ctx.past_decisions, list)

    def test_preferences_is_list(self, assembler, mission):
        ctx = assembler.assemble(mission)
        assert isinstance(ctx.preferences, list)

    def test_high_risk_mission(self, assembler):
        m = MissionContext(mission_id="m_r3", objective="Deploy to production", risk_level="R3")
        ctx = assembler.assemble(m)
        assert ctx is not None

    def test_adapter_retrieve_no_memory(self, adapter):
        results = adapter.retrieve("test query")
        assert results == []

    def test_adapter_broad_semantic_strategy(self, adapter):
        results = adapter.retrieve("test", strategy="broad_semantic")
        assert isinstance(results, list)

    def test_adapter_episodic_strategy(self, adapter):
        results = adapter.retrieve("test", strategy="episodic_match")
        assert isinstance(results, list)

    def test_adapter_progressive_retrieve(self, adapter):
        results = adapter.progressive_retrieve("test", 0.5)
        assert isinstance(results, list)

    def test_adapter_all_strategies_have_config(self, adapter):
        for strat in ["broad_semantic", "episodic_match", "working_context", "preference_bias", "procedural_rules"]:
            cfg = adapter.STRATEGIES.get(strat)
            assert cfg is not None, f"Missing config for {strat}"
            assert "layers" in cfg
            assert "top_k" in cfg
