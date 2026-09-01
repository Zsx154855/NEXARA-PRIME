"""V1.2 Intelligence Layer — Reflection Object Contracts.

Reflection captures the insight derived from an Evaluation and the policy for
how that insight should be persisted. No runtime-mutation field is permitted.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from nexara_prime.intelligence.evaluator.contracts import Evaluation
from nexara_prime.models import new_id

__all__ = ["Reflection"]


@dataclass
class Reflection:
    experience_id: str = field(default_factory=lambda: new_id("exp"))
    evaluation: Evaluation | None = None
    insight: str = ""
    memory_update_policy: str = "retain"  # retain | update_memory
