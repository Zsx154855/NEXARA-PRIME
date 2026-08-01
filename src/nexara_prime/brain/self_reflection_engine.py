"""SelfReflectionEngine — analyzes mission outcomes, extracts lessons, generates improvement scores."""

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
    """Analyzes mission outcomes, extracts lessons, scores improvement potential."""

    def __init__(self, memory_controller: MemoryController, experience_learner: ExperienceLearner | None = None) -> None:
        self._mc = memory_controller
        self._exp = experience_learner

    def record_reflection(
        self, mission_id: str, context_snapshot: dict[str, Any],
        action_summary: str, outcome_summary: str,
        success_signal: float, failure_signal: float,
        lessons: list[str] | None = None,
        evidence_id: str | None = None,
    ) -> str:
        entity = ReflectionEntity(
            mission_id=mission_id, context_snapshot=context_snapshot,
            action_summary=action_summary, outcome_summary=outcome_summary,
            success_signal=min(1.0, max(0.0, success_signal)),
            failure_signal=min(1.0, max(0.0, failure_signal)),
            lessons=lessons or [],
            improvement_score=self._compute_improvement(success_signal, failure_signal),
            confidence=0.7, evidence_id=evidence_id or "",
            created_at=now_iso(),
        )
        return self._mc.commit(
            mission_id=mission_id, key=f"reflection:{mission_id}",
            content=self._serialize(entity), kind="experience",
            evidence_id=evidence_id, confidence=entity.confidence,
        )

    def get_reflection(self, mission_id: str) -> ReflectionEntity | None:
        records = self._mc.recall(mission_id, layer="episodic")
        for r in records:
            if r.get("kind") == "experience" and r.get("key") == f"reflection:{mission_id}":
                return self._deserialize(r)
        return None

    def extract_lessons(self, mission_id: str) -> list[str]:
        reflection = self.get_reflection(mission_id)
        if reflection:
            return reflection.lessons
        return []

    def get_improvement_score(self, mission_id: str) -> float:
        reflection = self.get_reflection(mission_id)
        return reflection.improvement_score if reflection else 0.0

    def analyze_outcome(
        self, success: bool, similar_success_count: int = 0,
        similar_failure_count: int = 0, evidence_quality: float = 0.5,
    ) -> tuple[float, float]:
        if success:
            success_signal = 0.5 + 0.3 * min(1.0, similar_success_count / 10.0) + 0.2 * evidence_quality
            failure_signal = max(0.0, 0.3 - 0.1 * similar_success_count / 10.0)
        else:
            failure_signal = 0.5 + 0.3 * min(1.0, similar_failure_count / 10.0) + 0.2 * (1.0 - evidence_quality)
            success_signal = max(0.0, 0.3 - 0.1 * similar_success_count / 10.0)
        return success_signal, failure_signal

    def summarize(self) -> dict[str, Any]:
        records = self._mc.recall("global", layer="episodic")
        reflections = [self._deserialize(r) for r in records if r.get("key", "").startswith("reflection:")]
        reflections = [r for r in reflections if r is not None]
        avg_improvement = sum(r.improvement_score for r in reflections) / max(1, len(reflections))
        return {
            "total_reflections": len(reflections),
            "avg_improvement": round(avg_improvement, 3),
            "recent_lessons": [x for r in reflections[-5:] for x in r.lessons],
        }

    @staticmethod
    def _compute_improvement(success: float, failure: float) -> float:
        return round(success * 0.6 + (1.0 - failure) * 0.4, 3)

    @staticmethod
    def _serialize(entity: ReflectionEntity) -> str:
        return json.dumps({
            "mission_id": entity.mission_id,
            "context_snapshot": entity.context_snapshot,
            "action_summary": entity.action_summary,
            "outcome_summary": entity.outcome_summary,
            "success_signal": entity.success_signal,
            "failure_signal": entity.failure_signal,
            "lessons": entity.lessons,
            "improvement_score": entity.improvement_score,
            "confidence": entity.confidence,
            "evidence_id": entity.evidence_id,
            "created_at": entity.created_at,
        })

    @staticmethod
    def _deserialize(record: dict) -> ReflectionEntity | None:
        try:
            data = json.loads(record.get("content", "{}")) if isinstance(record.get("content"), str) else record.get("content", {})
            return ReflectionEntity(
                mission_id=data.get("mission_id", ""),
                context_snapshot=data.get("context_snapshot", {}),
                action_summary=data.get("action_summary", ""),
                outcome_summary=data.get("outcome_summary", ""),
                success_signal=float(data.get("success_signal", 0)),
                failure_signal=float(data.get("failure_signal", 0)),
                lessons=data.get("lessons", []),
                improvement_score=float(data.get("improvement_score", 0)),
                confidence=float(data.get("confidence", 0.5)),
                evidence_id=data.get("evidence_id", ""),
                created_at=data.get("created_at", ""),
            )
        except (json.JSONDecodeError, KeyError):
            return None
