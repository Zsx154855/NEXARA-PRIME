"""Consolidation rules for memory layer promotion.

Defines when and how memories move across layers:
  working → semantic: after access_count >= threshold
  episodic → semantic: automatic on mission completion
  semantic → procedural: after confidence >= threshold AND access_count >= threshold
"""

from __future__ import annotations

from ..models import MemoryKind

# ── Promotion thresholds ──

WORKING_TO_SEMANTIC_ACCESS_THRESHOLD = 3
SEMANTIC_TO_PROCEDURAL_CONFIDENCE_THRESHOLD = 0.9
SEMANTIC_TO_PROCEDURAL_ACCESS_THRESHOLD = 10

# ── Layer classification (mirrors MemoryController._classify_layer) ──

KIND_TO_LAYER: dict[str, str] = {
    MemoryKind.SHORT_TERM.value: "working",
    MemoryKind.TEMPORARY_CONTEXT.value: "working",
    MemoryKind.UNVERIFIED_INFERENCE.value: "working",
    MemoryKind.FACT.value: "semantic",
    MemoryKind.USER_FACT.value: "semantic",
    MemoryKind.PROJECT_FACT.value: "semantic",
    MemoryKind.PREFERENCE.value: "semantic",
    MemoryKind.DECISION.value: "episodic",
    MemoryKind.FAILURE.value: "episodic",
    MemoryKind.FAILURE_EXPERIENCE.value: "semantic",
    MemoryKind.PATCH.value: "procedural",
    MemoryKind.SKILL_IMPROVEMENT.value: "procedural",
    MemoryKind.SYSTEM_RULE.value: "procedural",
}


def classify_layer(kind: str) -> str:
    return KIND_TO_LAYER.get(kind, "semantic")


def should_promote_working_to_semantic(access_count: int) -> bool:
    return access_count >= WORKING_TO_SEMANTIC_ACCESS_THRESHOLD


def should_promote_semantic_to_procedural(confidence: float, access_count: int) -> bool:
    return (
        confidence >= SEMANTIC_TO_PROCEDURAL_CONFIDENCE_THRESHOLD
        and access_count >= SEMANTIC_TO_PROCEDURAL_ACCESS_THRESHOLD
    )


def can_consolidate_episodic_to_semantic(kind: str, layer: str) -> bool:
    """Episodic memories auto-consolidate to semantic on mission completion."""
    return layer == "episodic" and kind in {
        MemoryKind.DECISION.value,
        MemoryKind.FAILURE.value,
    }
