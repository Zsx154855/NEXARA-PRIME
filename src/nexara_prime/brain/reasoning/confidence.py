"""ConfidenceEngine — 5-factor weighted confidence evaluation.

Weights MUST sum to 1.0.
"""

from __future__ import annotations

from .models import ConfidenceScore

# Weights sum to 1.0
WEIGHTS = {
    "evidence_strength": 0.35,
    "consistency": 0.20,
    "completeness": 0.20,
    "source_reliability": 0.15,
    "historical_accuracy": 0.10,
}


class ConfidenceEngine:
    """Evaluates confidence of reasoning outputs using 5 weighted factors."""

    name = "confidence_engine"

    def evaluate(
        self,
        evidence_strength: float = 0.5,
        consistency: float = 0.5,
        completeness: float = 0.5,
        source_reliability: float = 0.5,
        historical_accuracy: float = 0.5,
    ) -> ConfidenceScore:
        """Compute weighted confidence score. All factors clamped to [0.0, 1.0]."""

        factors = {
            "evidence_strength": max(0.0, min(1.0, evidence_strength)),
            "consistency": max(0.0, min(1.0, consistency)),
            "completeness": max(0.0, min(1.0, completeness)),
            "source_reliability": max(0.0, min(1.0, source_reliability)),
            "historical_accuracy": max(0.0, min(1.0, historical_accuracy)),
        }

        score = sum(factors[k] * WEIGHTS[k] for k in WEIGHTS)
        score = round(max(0.0, min(1.0, score)), 4)

        level = self._classify_level(score)

        uncertainty_sources = []
        for k, v in factors.items():
            if v < 0.5:
                uncertainty_sources.append(f"low_{k}:{v:.2f}")

        return ConfidenceScore(
            score=score,
            level=level,
            factors=factors,
            uncertainty_sources=uncertainty_sources,
        )

    @staticmethod
    def _classify_level(score: float) -> str:
        if score >= 0.8:
            return "HIGH"
        if score >= 0.5:
            return "MEDIUM"
        if score >= 0.3:
            return "LOW"
        return "INSUFFICIENT"

    @staticmethod
    def weights_sum_to_one() -> bool:
        return abs(sum(WEIGHTS.values()) - 1.0) < 0.001
