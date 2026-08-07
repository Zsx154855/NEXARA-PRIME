"""Tests: EvolutionEngine — mission outcome observation tracking."""

import pytest

from src.nexara_prime.brain.evolution_engine import EvolutionEngine


@pytest.fixture
def engine():
    return EvolutionEngine()


class TestEvolutionEngineBasics:
    """Basic engine properties and empty state."""

    def test_name(self, engine):
        assert engine.name == "evolution_engine"

    def test_empty_observations(self, engine):
        assert engine._observations == []

    def test_insights_no_data(self, engine):
        result = engine.insights()
        assert result == {"status": "no_data"}

    def test_health_empty(self, engine):
        result = engine.health()
        assert result["observations"] == 0
        assert result["insights"] == {"status": "no_data"}


class TestObserve:
    """Recording mission outcome observations."""

    def test_observe_returns_obs_id(self, engine):
        obs_id = engine.observe("m1", "openai", "gpt-4o", True, 500, 0.002)
        assert obs_id.startswith("evo_")
        assert len(obs_id) > 4  # evo_ + hex

    def test_observe_appends_observation(self, engine):
        engine.observe("m1", "openai", "gpt-4o", True, 500, 0.002)
        assert len(engine._observations) == 1

    def test_observe_stores_required_fields(self, engine):
        obs_id = engine.observe("m1", "openai", "gpt-4o", True, 500, 0.002)
        obs = engine._observations[0]

        assert obs["observation_id"] == obs_id
        assert obs["mission_id"] == "m1"
        assert obs["provider"] == "openai"
        assert obs["model"] == "gpt-4o"
        assert obs["success"] is True
        assert obs["tokens"] == 500
        assert obs["cost"] == 0.002
        assert "timestamp" in obs

    def test_observe_stores_routing_decision(self, engine):
        routing = {"router": "cost_optimizer", "fallback": "deepseek"}
        engine.observe("m1", "openai", "gpt-4o", True, 500, 0.002, routing_decision=routing)
        assert engine._observations[0]["routing_decision"] == routing

    def test_observe_routing_decision_none_by_default(self, engine):
        engine.observe("m1", "openai", "gpt-4o", True, 500, 0.002)
        assert engine._observations[0]["routing_decision"] is None

    def test_observe_timestamp_is_iso_format(self, engine):
        engine.observe("m1", "openai", "gpt-4o", True, 500, 0.002)
        ts = engine._observations[0]["timestamp"]
        assert "T" in ts  # ISO 8601 separator
        assert ts.endswith("+00:00") or ts.endswith("Z")


class TestInsights:
    """Insight generation from observations."""

    def test_insights_single_success(self, engine):
        engine.observe("m1", "openai", "gpt-4o", True, 500, 0.002)
        result = engine.insights()

        assert result["total_missions"] == 1
        assert result["success_rate"] == 1.0
        assert result["total_cost"] == 0.002
        assert result["total_tokens"] == 500
        assert result["avg_tokens_per_mission"] == 500

    def test_insights_single_failure(self, engine):
        engine.observe("m1", "openai", "gpt-4o", False, 300, 0.001)
        result = engine.insights()

        assert result["total_missions"] == 1
        assert result["success_rate"] == 0.0

    def test_insights_success_rate_mixed(self, engine):
        engine.observe("m1", "openai", "gpt-4o", True, 100, 0.001)
        engine.observe("m2", "deepseek", "deepseek-v4", False, 200, 0.002)
        engine.observe("m3", "openai", "gpt-4o", True, 300, 0.003)

        result = engine.insights()

        assert result["total_missions"] == 3
        # 2/3 ≈ 0.67
        assert result["success_rate"] == round(2 / 3, 2)
        assert result["total_cost"] == round(0.006, 8)
        assert result["total_tokens"] == 600
        assert result["avg_tokens_per_mission"] == 200

    def test_insights_success_rate_all_succeed(self, engine):
        for i in range(5):
            engine.observe(f"m{i}", "openai", "gpt-4o", True, 100, 0.001)

        result = engine.insights()
        assert result["success_rate"] == 1.0

    def test_insights_success_rate_all_fail(self, engine):
        for i in range(5):
            engine.observe(f"m{i}", "openai", "gpt-4o", False, 100, 0.001)

        result = engine.insights()
        assert result["success_rate"] == 0.0

    def test_insights_unique_providers(self, engine):
        engine.observe("m1", "openai", "gpt-4o", True, 100, 0.001)
        engine.observe("m2", "deepseek", "deepseek-v4", True, 100, 0.001)
        engine.observe("m3", "openai", "gpt-4o", True, 100, 0.001)

        result = engine.insights()
        assert sorted(result["providers_used"]) == sorted(["openai", "deepseek"])

    def test_insights_unique_models(self, engine):
        engine.observe("m1", "openai", "gpt-4o", True, 100, 0.001)
        engine.observe("m2", "openai", "gpt-4o-mini", True, 100, 0.001)
        engine.observe("m3", "deepseek", "deepseek-v4", True, 100, 0.001)

        result = engine.insights()
        assert sorted(result["models_used"]) == sorted(["gpt-4o", "gpt-4o-mini", "deepseek-v4"])

    def test_insights_single_provider(self, engine):
        engine.observe("m1", "openai", "gpt-4o", True, 100, 0.001)
        engine.observe("m2", "openai", "gpt-4o-mini", True, 100, 0.001)

        result = engine.insights()
        assert result["providers_used"] == ["openai"]

    def test_insights_zero_cost(self, engine):
        engine.observe("m1", "openai", "gpt-4o", True, 500, 0.0)

        result = engine.insights()
        assert result["total_cost"] == 0.0

    def test_insights_token_sum_accurate(self, engine):
        engine.observe("m1", "openai", "gpt-4o", True, 1000, 0.001)
        engine.observe("m2", "openai", "gpt-4o", True, 2500, 0.002)
        engine.observe("m3", "openai", "gpt-4o", True, 150, 0.0005)

        result = engine.insights()
        assert result["total_tokens"] == 3650
        assert result["avg_tokens_per_mission"] == 1216


class TestHealth:
    """Health report generation."""

    def test_health_includes_observation_count(self, engine):
        engine.observe("m1", "openai", "gpt-4o", True, 100, 0.001)
        engine.observe("m2", "openai", "gpt-4o", True, 100, 0.001)

        result = engine.health()
        assert result["observations"] == 2

    def test_health_includes_insights(self, engine):
        engine.observe("m1", "openai", "gpt-4o", True, 100, 0.001)

        result = engine.health()
        assert "insights" in result
        assert result["insights"]["total_missions"] == 1

    def test_health_consistent_with_insights(self, engine):
        engine.observe("m1", "openai", "gpt-4o", True, 100, 0.001)

        health = engine.health()
        direct_insights = engine.insights()
        assert health["insights"] == direct_insights
