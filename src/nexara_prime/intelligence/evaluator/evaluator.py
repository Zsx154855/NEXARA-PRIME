"""V1.2 Evaluator Interface — mission result -> Evaluation.

Scoring engine only; never mutates V1.1 runtime state.
"""
from __future__ import annotations

from typing import Any

from .contracts import Evaluation

__all__ = ["EvaluationEngine"]


class EvaluationEngine:
    """Score a mission result into an Evaluation."""

    def evaluate(self, mission_result: dict[str, Any]) -> Evaluation:
        state = mission_result.get("current_state")
        success = state == "Completed"
        evidence_count = int(mission_result.get("evidence_count", 0))

        if evidence_count >= 10:
            quality = 0.9
        elif evidence_count >= 5:
            quality = 0.7
        else:
            quality = 0.4

        return Evaluation(
            mission_id=str(mission_result.get("mission_id", "")),
            quality_score=quality,
            success_score=1.0 if success else 0.0,
            cost_score=float(mission_result.get("cost_score", 0.0)),
            latency_ms=int(mission_result.get("latency_ms", 0)),
            failure_count=0 if success else 1,
            recovery_count=int(mission_result.get("recovery_count", 0)),
            recommendation="continue" if success else "retry",
        )
