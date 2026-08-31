"""V1.2 Intelligence Layer — Evaluator Object Contracts.

Evaluation is a first-class scoring object produced after a mission result.
Independent L2 overlay; read-only over V1.1 (no Runtime Core / SQLite import).
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Evaluation"]


@dataclass
class Evaluation:
    mission_id: str = ""
    quality_score: float = 0.0
    success_score: float = 0.0
    cost_score: float = 0.0
    latency_ms: int = 0
    failure_count: int = 0
    recovery_count: int = 0
    recommendation: str = "retry"  # continue | retry
