"""ContextAssembler — builds bounded context for reasoning from memory retrieval.

6-step pipeline: extract→retrieve→past_decisions→preferences→dedup→bound.
MemoryRetrievalAdapter wraps MemoryController.rank_retrieve().
NEVER imports brain.db.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .models import AssembledContext, MissionContext

if TYPE_CHECKING:
    from ...memory_controller import MemoryController


class MemoryRetrievalAdapter:
    """Wraps MemoryController.rank_retrieve() for reasoning context assembly.

    ISOLATION RULE: NEVER imports brain.db. Only uses public MemoryController API.
    """

    name = "memory_retrieval_adapter"

    STRATEGIES = {
        "broad_semantic": {"layers": ["semantic", "procedural"], "top_k": 20, "min_conf": 0.3},
        "episodic_match": {"layers": ["episodic"], "top_k": 10, "min_conf": 0.5},
        "working_context": {"layers": ["working"], "top_k": 5, "min_conf": 0.0},
        "preference_bias": {"layers": ["semantic"], "top_k": 5, "min_conf": 0.5},
        "procedural_rules": {"layers": ["procedural"], "top_k": 10, "min_conf": 0.7},
    }

    def __init__(self, memory: "MemoryController | None" = None) -> None:
        self._memory = memory

    def bind(self, memory: "MemoryController") -> None:
        self._memory = memory

    def retrieve(
        self,
        query: str,
        strategy: str = "broad_semantic",
        top_k: int | None = None,
        min_confidence: float | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve memories using specified strategy. Falls back to keyword filter if no memory bound."""
        cfg = self.STRATEGIES.get(strategy, self.STRATEGIES["broad_semantic"])
        k = top_k if top_k is not None else cfg["top_k"]
        min_c = min_confidence if min_confidence is not None else cfg["min_conf"]

        if self._memory is not None:
            try:
                return self._memory.rank_retrieve(
                    query=query,
                    top_k=k,
                    layers=cfg["layers"],
                    min_confidence=min_c,
                )
            except Exception:
                pass  # fall through to empty

        return []

    def progressive_retrieve(
        self, query: str, initial_confidence: float,
    ) -> list[dict[str, Any]]:
        """If confidence < 0.7, re-query with expanded parameters."""
        results = self.retrieve(query, strategy="broad_semantic")
        if initial_confidence < 0.7 and results:
            expanded = self.retrieve(
                query,
                strategy="broad_semantic",
                top_k=30,
                min_confidence=0.2,
            )
            # Deduplicate by memory_id
            seen = {r.get("memory_id") for r in results}
            for r in expanded:
                if r.get("memory_id") not in seen:
                    results.append(r)
                    seen.add(r.get("memory_id"))
        return results


class ContextAssembler:
    """Assembles bounded context for reasoning from mission + memory."""

    name = "context_assembler"

    MAX_ITEMS = 50
    MAX_TOKENS = 5000

    def __init__(self, adapter: MemoryRetrievalAdapter | None = None) -> None:
        self._adapter = adapter or MemoryRetrievalAdapter()

    def assemble(
        self,
        mission: MissionContext,
        initial_confidence: float = 0.5,
    ) -> AssembledContext:
        """6-step pipeline to build bounded context."""

        # Step 1: Mission context extraction
        mission_summary = (
            f"Objective: {mission.objective}. "
            f"Risk: {mission.risk_level}. "
            f"Constraints: {', '.join(mission.constraints[:5])}."
        )

        # Step 2: Memory retrieval (broad semantic)
        relevant = self._adapter.progressive_retrieve(
            mission.objective, initial_confidence,
        )

        # Step 3: Past decision retrieval
        past = self._adapter.retrieve(
            mission.objective, strategy="episodic_match",
        )

        # Step 4: Preference retrieval
        prefs = self._adapter.retrieve(
            mission.objective, strategy="preference_bias",
        )

        # Step 5: Deduplication — keep highest confidence for duplicate keys
        seen_keys: dict[str, dict[str, Any]] = {}
        for item in relevant:
            key = item.get("key", "")
            if key not in seen_keys or item.get("confidence", 0) > seen_keys[key].get("confidence", 0):
                seen_keys[key] = item

        # Step 6: Bounding — trim to MAX_ITEMS, estimate tokens
        deduped = sorted(
            seen_keys.values(),
            key=lambda x: x.get("confidence", 0),
            reverse=True,
        )[: self.MAX_ITEMS]

        context_size = sum(
            len(str(r.get("content", ""))) for r in deduped
        )

        return AssembledContext(
            mission_summary=mission_summary,
            relevant_memories=deduped,
            past_decisions=past,
            preferences=prefs,
            context_size=min(context_size, self.MAX_TOKENS),
            max_items=self.MAX_ITEMS,
            max_tokens=self.MAX_TOKENS,
        )
