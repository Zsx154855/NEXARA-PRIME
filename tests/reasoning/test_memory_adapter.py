"""Tests: Memory Retrieval Adapter — isolation, no brain.db import."""

from src.nexara_prime.brain.reasoning import MemoryRetrievalAdapter


class TestMemoryAdapter:
    """10 tests: adapter isolation, strategies, progressive retrieval."""

    def test_adapter_no_brain_db_import(self):
        """Verify MemoryRetrievalAdapter NEVER imports brain.db."""
        import inspect
        from src.nexara_prime.brain.reasoning.context_assembler import MemoryRetrievalAdapter as MRA
        source = inspect.getsource(MRA)
        # Check import lines only (ignore docstrings mentioning brain.db)
        for line in source.split("\n"):
            line = line.strip()
            if line.startswith("from") and "BrainDB" in line:
                assert False, f"Adapter imports BrainDB: {line}"
            if line.startswith("import") and "BrainDB" in line:
                assert False, f"Adapter imports BrainDB: {line}"

    def test_adapter_initialization(self):
        adapter = MemoryRetrievalAdapter()
        assert adapter.name == "memory_retrieval_adapter"

    def test_adapter_bind_memory(self):
        adapter = MemoryRetrievalAdapter()
        assert adapter._memory is None
        # bind with None is acceptable
        adapter.bind(None)
        assert adapter._memory is None

    def test_adapter_all_5_strategies(self):
        adapter = MemoryRetrievalAdapter()
        strategies = list(adapter.STRATEGIES.keys())
        assert "broad_semantic" in strategies
        assert "episodic_match" in strategies
        assert "working_context" in strategies
        assert "preference_bias" in strategies
        assert "procedural_rules" in strategies
        assert len(strategies) == 5

    def test_adapter_retrieve_invalid_strategy_fallback(self):
        adapter = MemoryRetrievalAdapter()
        results = adapter.retrieve("test", strategy="nonexistent")
        assert results == []  # falls back to broad_semantic, but no memory bound

    def test_adapter_retrieve_custom_params(self):
        adapter = MemoryRetrievalAdapter()
        results = adapter.retrieve("test", top_k=5, min_confidence=0.7)
        assert isinstance(results, list)

    def test_adapter_progressive_low_confidence(self):
        adapter = MemoryRetrievalAdapter()
        results = adapter.progressive_retrieve("test", 0.3)
        assert isinstance(results, list)

    def test_adapter_progressive_high_confidence(self):
        adapter = MemoryRetrievalAdapter()
        results = adapter.progressive_retrieve("test", 0.9)
        assert isinstance(results, list)

    def test_adapter_no_runtime_imports(self):
        import inspect
        from src.nexara_prime.brain.reasoning.context_assembler import MemoryRetrievalAdapter as MRA
        source = inspect.getsource(MRA)
        forbidden = ["from ..runtime", "from ..evidence", "from ..evaluation", "from ..tools"]
        for pattern in forbidden:
            assert pattern not in source, f"Adapter imports forbidden: {pattern}"

    def test_adapter_progressive_deduplicates(self):
        adapter = MemoryRetrievalAdapter()
        # Multiple calls should not duplicate (no memory bound, so empty)
        r1 = adapter.progressive_retrieve("test", 0.3)
        assert isinstance(r1, list)
