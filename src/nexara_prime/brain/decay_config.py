"""Decay configuration for memory kinds.

Defines half-life and confidence parameters per MemoryKind.
Never-decay kinds use half_life_seconds=0 (superseded/versioned instead).
"""

from __future__ import annotations

from ..models import MemoryKind

# Half-life in seconds per MemoryKind.
# 0 = never decays (superseded or versioned instead of time-based decay)
DECAY_HALF_LIFE: dict[str, int] = {
    MemoryKind.SHORT_TERM.value: 3600,               # 1 hour
    MemoryKind.TEMPORARY_CONTEXT.value: 86400,        # 1 day (1 mission)
    MemoryKind.UNVERIFIED_INFERENCE.value: 1800,      # 30 minutes
    MemoryKind.FACT.value: 7776000,                   # 90 days
    MemoryKind.USER_FACT.value: 15552000,             # 180 days
    MemoryKind.PROJECT_FACT.value: 31536000,          # 365 days
    MemoryKind.PREFERENCE.value: 7776000,             # 90 days
    MemoryKind.DECISION.value: 0,                     # Never decays
    MemoryKind.FAILURE.value: 0,                      # Never decays
    MemoryKind.FAILURE_EXPERIENCE.value: 15552000,    # 180 days
    MemoryKind.PATCH.value: 0,                        # Never decays (versioned)
    MemoryKind.SKILL_IMPROVEMENT.value: 0,            # Never decays (versioned)
    MemoryKind.SYSTEM_RULE.value: 0,                  # Never decays
}

# Minimum confidence floor per kind
DECAY_MIN_CONFIDENCE: dict[str, float] = {
    MemoryKind.SHORT_TERM.value: 0.1,
    MemoryKind.TEMPORARY_CONTEXT.value: 0.1,
    MemoryKind.UNVERIFIED_INFERENCE.value: 0.05,
    MemoryKind.FACT.value: 0.3,
    MemoryKind.USER_FACT.value: 0.5,
    MemoryKind.PROJECT_FACT.value: 0.5,
    MemoryKind.PREFERENCE.value: 0.3,
    MemoryKind.DECISION.value: 0.9,
    MemoryKind.FAILURE.value: 0.9,
    MemoryKind.FAILURE_EXPERIENCE.value: 0.3,
    MemoryKind.PATCH.value: 0.9,
    MemoryKind.SKILL_IMPROVEMENT.value: 0.9,
    MemoryKind.SYSTEM_RULE.value: 0.9,
}


def compute_decayed_confidence(
    initial_confidence: float,
    half_life_seconds: int,
    elapsed_seconds: float,
    min_confidence: float = 0.0,
) -> float:
    """Exponential decay: confidence = initial * (0.5 ^ (elapsed / half_life))."""
    if half_life_seconds <= 0:
        return initial_confidence  # never decays
    if elapsed_seconds <= 0:
        return initial_confidence
    decay_factor = 0.5 ** (elapsed_seconds / half_life_seconds)
    decayed = initial_confidence * decay_factor
    return max(decayed, min_confidence)


def get_half_life(kind: str) -> int:
    return DECAY_HALF_LIFE.get(kind, 7776000)  # default 90 days


def get_min_confidence(kind: str) -> float:
    return DECAY_MIN_CONFIDENCE.get(kind, 0.1)
