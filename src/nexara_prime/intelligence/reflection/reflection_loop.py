"""V1.2 Reflection Loop — Evaluation -> Reflection.

Produces an insight + memory-update policy. Deliberately carries NO
self-modify-runtime capability: no method mutates V1.1 runtime state.
"""
from __future__ import annotations

from nexara_prime.intelligence.evaluator.contracts import Evaluation

from .contracts import Reflection

__all__ = ["ReflectionLoop"]


class ReflectionLoop:
    """Turn an Evaluation into a Reflection. Read-only; no runtime mutation."""

    def reflect(self, evaluation: Evaluation) -> Reflection:
        if evaluation.success_score >= 1.0:
            return Reflection(
                evaluation=evaluation,
                insight="keep strategy",
                memory_update_policy="retain",
            )
        return Reflection(
            evaluation=evaluation,
            insight="adjust strategy",
            memory_update_policy="update_memory",
        )
