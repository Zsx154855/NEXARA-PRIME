"""Experience Recall — queries past mission experiences for the feedback loop.

Enables the Chief Brain to recall similar missions, predict risk based on
history, and recommend strategies from past successes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nexara_prime.brain.experience_store import ExperienceStore, MissionExperience


@dataclass(frozen=True)
class RecallResult:
    """Result of an experience recall query."""
    query: str
    matches: list[MissionExperience]
    total_matches: int
    relevance_scores: list[float] = field(default_factory=list)
    recommended_strategy: str = ""


class ExperienceRecall:
    """Queries past experiences for feedback loop intelligence.

    Supports:
      - Similar mission recall (by objective keywords).
      - Risk prediction (based on historical outcomes).
      - Adapter recommendation (based on past success rates).
      - Lesson aggregation (top lessons from similar missions).
    """

    def __init__(self, store: ExperienceStore) -> None:
        self._store = store

    def search(self, query: str, *, limit: int = 10) -> RecallResult:
        """Search for experiences matching a query string.

        Simple keyword matching against mission objectives.
        """
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        scored: list[tuple[float, MissionExperience]] = []
        for exp in self._store.list_all():
            obj_lower = exp.objective.lower()
            # Score by term overlap
            term_hits = sum(1 for t in query_terms if t in obj_lower)
            if term_hits > 0:
                score = term_hits / len(query_terms)
                scored.append((score, exp))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:limit]
        matches = [s[1] for s in top]
        scores = [round(s[0], 4) for s in top]

        strategy = self._recommend_strategy(matches)

        return RecallResult(
            query=query,
            matches=matches,
            total_matches=len(scored),
            relevance_scores=scores,
            recommended_strategy=strategy,
        )

    def predict_risk(self, objective: str) -> dict[str, Any]:
        """Predict mission risk based on similar past experiences."""
        similar = self.search(objective, limit=10)
        if not similar.matches:
            return {"predicted_risk": "R2", "confidence": 0.0, "based_on": 0}

        # Weight by relevance score
        total_weight = sum(similar.relevance_scores)
        risk_weights: dict[str, float] = {}
        for i, exp in enumerate(similar.matches):
            w = similar.relevance_scores[i] / max(total_weight, 0.001)
            risk_weights[exp.risk_level] = risk_weights.get(exp.risk_level, 0.0) + w

        best_risk = max(risk_weights, key=risk_weights.get)
        confidence = risk_weights[best_risk]

        return {
            "predicted_risk": best_risk,
            "confidence": round(confidence, 4),
            "based_on": len(similar.matches),
            "risk_distribution": {k: round(v, 4) for k, v in risk_weights.items()},
        }

    def recommend_adapter(self, objective: str) -> dict[str, Any]:
        """Recommend the best adapter based on past success rates."""
        similar = self.search(objective, limit=20)
        if not similar.matches:
            return {"recommended_adapter": "claude", "confidence": 0.0}

        adapter_stats: dict[str, dict[str, float]] = {}
        for exp in similar.matches:
            if exp.adapter not in adapter_stats:
                adapter_stats[exp.adapter] = {"successes": 0, "total": 0}
            adapter_stats[exp.adapter]["total"] += 1
            if exp.status == "success":
                adapter_stats[exp.adapter]["successes"] += 1

        ranked = []
        for adapter, stats in adapter_stats.items():
            rate = stats["successes"] / max(stats["total"], 1)
            ranked.append((rate, adapter))

        ranked.sort(reverse=True)
        if not ranked:
            return {"recommended_adapter": "claude", "confidence": 0.0}

        return {
            "recommended_adapter": ranked[0][1],
            "confidence": round(ranked[0][0], 4),
            "alternatives": [r[1] for r in ranked[1:3]],
            "based_on": len(similar.matches),
        }

    def top_lessons(self, limit: int = 10) -> list[str]:
        """Aggregate top lessons from high-score experiences."""
        all_exp = sorted(
            [e for e in self._store.list_all() if e.score >= 0.5],
            key=lambda e: e.score,
            reverse=True,
        )
        seen: set[str] = set()
        lessons: list[str] = []
        for exp in all_exp:
            for lesson in exp.lessons:
                if lesson not in seen:
                    seen.add(lesson)
                    lessons.append(lesson)
                    if len(lessons) >= limit:
                        return lessons
        return lessons

    @staticmethod
    def _recommend_strategy(matches: list[MissionExperience]) -> str:
        if not matches:
            return "no_historical_data"
        success_rate = sum(1 for e in matches if e.status == "success") / len(matches)
        if success_rate >= 0.8:
            return "follow_successful_pattern"
        elif success_rate >= 0.5:
            return "adapt_with_caution"
        else:
            return "try_alternative_approach"
