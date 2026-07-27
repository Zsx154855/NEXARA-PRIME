"""Tests: Confidence Engine — 5 factors, weights sum to 1.0, levels."""

import pytest
from src.nexara_prime.brain.reasoning import ConfidenceEngine, WEIGHTS


@pytest.fixture
def engine():
    return ConfidenceEngine()


class TestConfidence:
    """10 tests: factor calculation, weight validation, level classification."""

    def test_weights_sum_to_one(self):
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_weights_sum_to_one_method(self):
        engine = ConfidenceEngine()
        assert engine.weights_sum_to_one()

    def test_evaluate_returns_score(self, engine):
        result = engine.evaluate(0.8, 0.7, 0.6, 0.9, 0.5)
        assert 0.0 <= result.score <= 1.0

    def test_evaluate_all_high(self, engine):
        result = engine.evaluate(1.0, 1.0, 1.0, 1.0, 1.0)
        assert result.score > 0.9
        assert result.level == "HIGH"

    def test_evaluate_all_low(self, engine):
        result = engine.evaluate(0.1, 0.1, 0.1, 0.1, 0.1)
        assert result.score < 0.3
        assert result.level == "INSUFFICIENT"

    def test_evaluate_medium(self, engine):
        result = engine.evaluate(0.6, 0.6, 0.6, 0.6, 0.6)
        assert result.level == "MEDIUM"

    def test_evaluate_clamps_inputs(self, engine):
        result = engine.evaluate(2.0, -1.0, 1.5, -0.5, 3.0)
        assert 0.0 <= result.score <= 1.0

    def test_high_level(self, engine):
        result = engine.evaluate(0.9, 0.9, 0.9, 0.9, 0.9)
        assert result.level == "HIGH"

    def test_low_level(self, engine):
        result = engine.evaluate(0.4, 0.4, 0.4, 0.4, 0.4)
        assert result.level == "LOW"

    def test_uncertainty_sources_tracked(self, engine):
        result = engine.evaluate(0.2, 0.5, 0.5, 0.5, 0.5)
        assert len(result.uncertainty_sources) > 0

    def test_five_factors_in_result(self, engine):
        result = engine.evaluate(0.5, 0.5, 0.5, 0.5, 0.5)
        assert len(result.factors) == 5
        assert "evidence_strength" in result.factors
        assert "consistency" in result.factors
        assert "completeness" in result.factors
        assert "source_reliability" in result.factors
        assert "historical_accuracy" in result.factors
