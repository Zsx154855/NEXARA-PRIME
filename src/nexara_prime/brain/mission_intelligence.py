"""Mission intelligence layer for strategy and risk projections."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from ..models import now_iso

if TYPE_CHECKING:
    from .experience_learner import ExperienceLearner
    from .memory_controller import MemoryController
    from .preference_model import PreferenceModel


@dataclass
class MissionInsight:
    recommended_strategy: str
    risk_prediction: float
    confidence: float
    similar_missions: list[str] = field(default_factory=list)
    evidence_references: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class MissionIntelligenceLayer:
    """Recommend strategies, predict risk, and match mission history."""

    def __init__(self, memory_controller: MemoryController, preference_model: PreferenceModel | None = None, experience_learner: ExperienceLearner | None = None) -> None:
        self._mc = memory_controller
        self._pref = preference_model
        self._exp = experience_learner

    def analyze_mission(self, mission: dict[str, Any]) -> MissionInsight:
        objective = mission.get("objective", "")
        similar = self._find_similar_missions(objective, limit=5)
        risk = self._predict_risk(objective, similar, mission.get("risk_level", "medium"))
        strategy = self._recommend_strategy(mission.get("type", "unknown"), similar, objective)
        return MissionInsight(
            recommended_strategy=strategy,
            risk_prediction=risk,
            confidence=0.7 if len(similar) >= 3 else 0.4,
            similar_missions=[s.get("mission_id", "") for s in similar],
            evidence_references=[s.get("evidence_id", "") for s in similar if s.get("evidence_id")],
            warnings=self._generate_warnings(risk, similar),
        )

    def recommend_strategy(self, mission: dict[str, Any]) -> str:
        return self.analyze_mission(mission).recommended_strategy

    def predict_risk(self, mission: dict[str, Any]) -> float:
        return self.analyze_mission(mission).risk_prediction

    def get_similar_missions(self, objective: str, limit: int = 10) -> list[dict[str, Any]]:
        return self._find_similar_missions(objective, limit)

    def record_mission_insight(self, mission_id: str, insight: MissionInsight, evidence_id: str | None = None) -> str:
        content = json.dumps({"mission_id": mission_id, "recommended_strategy": insight.recommended_strategy, "risk_prediction": insight.risk_prediction, "confidence": insight.confidence, "similar_missions": insight.similar_missions, "evidence_references": insight.evidence_references, "warnings": insight.warnings, "created_at": now_iso()})
        return self._mc.commit(mission_id=mission_id, key=f"insight:{mission_id}", content=content, kind="procedural", evidence_id=evidence_id, confidence=insight.confidence)

    def get_mission_insight(self, mission_id: str) -> MissionInsight | None:
        for record in self._mc.recall(mission_id, layer="procedural"):
            if record.get("kind") == "procedural" and record.get("key") == f"insight:{mission_id}":
                try:
                    data = json.loads(record.get("content", "{}"))
                    return MissionInsight(data.get("recommended_strategy", ""), float(data.get("risk_prediction", 0.5)), float(data.get("confidence", 0.5)), data.get("similar_missions", []), data.get("evidence_references", []), data.get("warnings", []))
                except (json.JSONDecodeError, KeyError, TypeError):
                    return None
        return None

    def summarize(self) -> dict[str, Any]:
        records = self._mc.recall("global", layer="procedural")
        insights = [r for r in records if r.get("key", "").startswith("insight:")]
        avg = sum(float(r.get("confidence", 0.5)) for r in insights) / max(1, len(insights))
        return {"total_insights": len(insights), "avg_confidence": round(avg, 3)}

    def _find_similar_missions(self, objective: str, limit: int = 5) -> list[dict[str, Any]]:
        if self._exp:
            experiences = self._exp.rank_experiences(objective, top_k=limit)
            return [{"mission_id": e.mission_id, "outcome": e.outcome, "success": e.success, "action": e.action, "evidence_id": e.evidence_id} for e in experiences]
        records = self._mc.rank_retrieve(query=objective, top_k=limit, layers=["episodic"], min_confidence=0.1)
        return [{"mission_id": r.get("mission_id", ""), "outcome": "", "success": True, "action": "", "evidence_id": r.get("evidence_id", "")} for r in records]

    def _predict_risk(self, objective: str, similar: list[dict[str, Any]], risk_level: str) -> float:
        if not similar:
            return {"low": 0.3, "medium": 0.5, "high": 0.8}[risk_level]
        failure_rate = sum(1 for s in similar if not s.get("success", True)) / len(similar)
        return round(min(1.0, {"low": 0.2, "medium": 0.5, "high": 0.8}.get(risk_level, 0.5) * 0.5 + failure_rate * 0.5), 3)

    @staticmethod
    def _recommend_strategy(mission_type: str, similar: list[dict[str, Any]], objective: str) -> str:
        successful = [s.get("action", "") for s in similar if s.get("success")]
        if successful:
            return f"Reuse successful pattern: {successful[0][:80]}"
        return "Proceed with standard execution — no historical pattern available"

    @staticmethod
    def _generate_warnings(risk: float, similar: list[dict[str, Any]]) -> list[str]:
        warnings = []
        if risk > 0.7:
            warnings.append(f"High predicted risk ({risk:.0%}) — consider human review")
        if not similar:
            warnings.append("No similar missions found — first-of-kind execution")
        failures = sum(1 for s in similar if not s.get("success", True))
        if failures:
            warnings.append(f"{failures}/{len(similar)} similar missions failed — review failure patterns")
        return warnings
