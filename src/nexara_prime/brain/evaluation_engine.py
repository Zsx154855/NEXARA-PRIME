"""Evaluation Engine — scores mission execution outcomes for the feedback loop.

Scores missions on: success criteria completion, risk accuracy,
execution quality, and learning potential. Feeds ExperienceStore
for continuous improvement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MissionScore:
    """Comprehensive mission evaluation score."""
    mission_id: str
    total_score: float  # 0.0 - 1.0
    success_criteria_met: int
    success_criteria_total: int
    risk_accuracy: float  # was the risk prediction correct?
    execution_efficiency: float  # tokens used vs estimated
    learning_value: float  # how valuable is this experience?
    areas_for_improvement: list[str] = field(default_factory=list)
    grade: str = "C"  # A/B/C/D/F


class EvaluationEngine:
    """Deterministic mission outcome evaluator.

    Scores missions based on objective criteria. No model calls.
    Results feed the ExperienceStore for future planning improvement.
    """

    # Scoring weights
    _SUCCESS_WEIGHT = 0.40
    _RISK_ACCURACY_WEIGHT = 0.25
    _EXECUTION_WEIGHT = 0.20
    _LEARNING_WEIGHT = 0.15

    def evaluate(
        self,
        mission_id: str,
        *,
        success_criteria_met: int = 0,
        success_criteria_total: int = 1,
        predicted_risk: str = "R2",
        actual_risk_drift: float = 0.0,
        estimated_tokens: int = 0,
        actual_tokens: int = 0,
        lessons_learned: list[str] | None = None,
    ) -> MissionScore:
        """Evaluate a mission execution outcome.

        Args:
            mission_id: Unique mission identifier.
            success_criteria_met: Number of success criteria achieved.
            success_criteria_total: Total success criteria.
            predicted_risk: The risk level predicted by MIE.
            actual_risk_drift: How much the actual risk deviated (0.0 = perfect).
            estimated_tokens: Estimated token count.
            actual_tokens: Actual token count used.
            lessons_learned: List of lessons from this mission.

        Returns:
            MissionScore with total_score, grade, and improvement areas.
        """
        total = max(success_criteria_total, 1)

        # Success criteria score
        success_score = success_criteria_met / total

        # Risk accuracy score (lower drift = higher score)
        risk_score = max(0.0, 1.0 - actual_risk_drift)

        # Execution efficiency (closer to estimate = higher score)
        if estimated_tokens > 0:
            ratio = actual_tokens / estimated_tokens
            execution_score = 1.0 - abs(1.0 - min(ratio, 2.0)) / 2.0
        else:
            execution_score = 0.5  # neutral

        # Learning value (more lessons = more valuable)
        lesson_count = len(lessons_learned or [])
        learning_score = min(1.0, lesson_count * 0.25)

        total_score = (
            success_score * self._SUCCESS_WEIGHT
            + risk_score * self._RISK_ACCURACY_WEIGHT
            + execution_score * self._EXECUTION_WEIGHT
            + learning_score * self._LEARNING_WEIGHT
        )

        # Grade assignment
        if total_score >= 0.90:
            grade = "A"
        elif total_score >= 0.75:
            grade = "B"
        elif total_score >= 0.55:
            grade = "C"
        elif total_score >= 0.35:
            grade = "D"
        else:
            grade = "F"

        # Improvement areas
        improvements: list[str] = []
        if success_score < 0.8:
            improvements.append("improve_success_criteria_completion")
        if risk_score < 0.7:
            improvements.append("improve_risk_assessment_accuracy")
        if execution_score < 0.6:
            improvements.append("improve_execution_efficiency")
        if learning_score < 0.5:
            improvements.append("increase_lesson_capture")

        return MissionScore(
            mission_id=mission_id,
            total_score=round(total_score, 4),
            success_criteria_met=success_criteria_met,
            success_criteria_total=total,
            risk_accuracy=round(risk_score, 4),
            execution_efficiency=round(execution_score, 4),
            learning_value=round(learning_score, 4),
            areas_for_improvement=improvements,
            grade=grade,
        )

    def batch_evaluate(
        self,
        evaluations: list[dict[str, Any]],
    ) -> list[MissionScore]:
        """Evaluate multiple missions at once."""
        return [self.evaluate(**ev) for ev in evaluations]

    def aggregate_stats(self, scores: list[MissionScore]) -> dict[str, Any]:
        if not scores:
            return {"avg_score": 0.0, "grade_distribution": {}, "total": 0}
        avg = sum(s.total_score for s in scores) / len(scores)
        grades: dict[str, int] = {}
        for s in scores:
            grades[s.grade] = grades.get(s.grade, 0) + 1
        return {
            "avg_score": round(avg, 4),
            "grade_distribution": grades,
            "total": len(scores),
        }
