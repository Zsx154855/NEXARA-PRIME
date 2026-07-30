"""SelfReflectionEngine — analyzes mission outcomes and extracts lessons."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from ..models import now_iso

if TYPE_CHECKING:
    from .memory_controller import MemoryController
    from .experience_learner import ExperienceLearner


@dataclass
class ReflectionEntity:
    mission_id: str
    context_snapshot: dict[str, Any]
    action_summary: str
    outcome_summary: str
    success_signal: float
    failure_signal: float
    lessons: list[str] = field(default_factory=list)
    improvement_score: float = 0.0
    confidence: float = 0.5
    evidence_id: str = ""
    created_at: str = ""


class SelfReflectionEngine:
    """Analyzes mission outcomes, extracts lessons, scores improvement."""

    def __init__(self, memory_controller: MemoryController, experience_learner: ExperienceLearner | None = None) -> None:
        self._mc = memory_controller
        self._exp = experience_learner

    def record_reflection(
        self, mission_id: str, context_snapshot: dict[str, Any],
        action_summary: str, outcome_summary: str,
        success_signal: float, failure_signal: float,
        lessons: list[str] | None = None, evidence_id: str | None = None,
    ) -> str:
        entity = ReflectionEntity(
            mission_id=mission_id, context_snapshot=context_snapshot,
            action_summary=action_summary, outcome_summary=outcome_summary,
            success_signal=min(1.0, max(0.0, success_signal)),
            failure_signal=min(1.0, max(0.0, failure_signal)),
            lessons=lessons or [],
            improvement_score=self._compute_improvement(success_signal, failure_signal),
            confidence=0.7, evidence_id=evidence_id or "", created_at=now_iso(),
        )
        return self._mc.commit(
            mission_id=mission_id, key=f"reflection:{mission_id}",
            content=self._serialize(entity), kind="experience",
            evidence_id=evidence_id, confidence=entity.confidence,
        )

    def get_reflection(self, mission_id: str) -> ReflectionEntity | None:
        for record in self._mc.recall(mission_id, layer="episodic"):
            if record.get("kind") == "experience" and record.get("key") == f"reflection:{mission_id}":
                return self._deserialize(record)
        return None

    def extract_lessons(self, mission_id: str) -> list[str]:
        reflection = self.get_reflection(mission_id)
        return reflection.lessons if reflection else []

    def get_improvement_score(self, mission_id: str) -> float:
        reflection = self.get_reflection(mission_id)
        return reflection.improvement_score if reflection else 0.0

    def analyze_outcome(self, success: bool, similar_success_count: int = 0, similar_failure_count: int = 0, evidence_quality: float = 0.5) -> tuple[float, float]:
        if success:
            return (0.5 + 0.3 * min(1.0, similar_success_count / 10.0) + 0.2 * evidence_quality,
                    max(0.0, 0.3 - 0.1 * similar_success_count / 10.0))
        return (max(0.0, 0.3 - 0.1 * similar_success_count / 10.0),
                0.5 + 0.3 * min(1.0, similar_failure_count / 10.0) + 0.2 * (1.0 - evidence_quality))

    def summarize(self) -> dict[str, Any]:
        reflections = [self._deserialize(r) for r in self._mc.recall("global", layer="episodic") if r.get("key", "").startswith("reflection:")]
        reflections = [r for r in reflections if r is not None]
        avg = sum(r.improvement_score for r in reflections) / max(1, len(reflections))
        return {"total_reflections": len(reflections), "avg_improvement": round(avg, 3), "recent_lessons": [x for r in reflections[-5:] for x in r.lessons]}

    @staticmethod
    def _compute_improvement(success: float, failure: float) -> float:
        return round(success * 0.6 + (1.0 - failure) * 0.4, 3)

    @staticmethod
    def _serialize(entity: ReflectionEntity) -> str:
        return json.dumps(entity.__dict__)

    @staticmethod
    def _deserialize(record: dict[str, Any]) -> ReflectionEntity | None:
        try:
            data = json.loads(record.get("content", "{}")) if isinstance(record.get("content"), str) else record.get("content", {})
            return ReflectionEntity(**data)
        except (json.JSONDecodeError, TypeError, KeyError):
            return None
