"""Tests: Decision Framework — 6-step process, evidence weighting."""

import pytest
from src.nexara_prime.brain.reasoning import DecisionFramework, DecisionOption, ConfidenceScore


@pytest.fixture
def decider():
    return DecisionFramework()


class TestDecisionFramework:
    """10 tests: decision process, evidence weighting, alternatives."""

    def test_decide_returns_decision(self, decider):
        options = [DecisionOption(option_id="opt1", description="Use flash model", confidence=0.8)]
        result = decider.decide("Which model?", options)
        assert result.decision_id.startswith("dec_")

    def test_decide_selects_highest_confidence(self, decider):
        options = [
            DecisionOption(option_id="low", description="Low conf option", confidence=0.3),
            DecisionOption(option_id="high", description="High conf option", confidence=0.9),
        ]
        result = decider.decide("Test", options)
        assert result.selected_option == "high"

    def test_decide_with_evidence(self, decider):
        options = [
            DecisionOption(option_id="opt1", description="With evidence", evidence=["ev1", "ev2"], confidence=0.7),
            DecisionOption(option_id="opt2", description="No evidence", confidence=0.7),
        ]
        result = decider.decide("Test", options)
        assert result.selected_option == "opt1"  # evidence gives weight boost

    def test_decide_no_options(self, decider):
        result = decider.decide("Test", [])
        assert result.selected_option == "none"
        assert result.confidence == 0.0

    def test_decide_single_option(self, decider):
        options = [DecisionOption(option_id="only", description="Only option")]
        result = decider.decide("Test", options)
        assert result.selected_option == "only"

    def test_decide_reason_contains_details(self, decider):
        options = [DecisionOption(option_id="opt1", description="Test option", confidence=0.8)]
        result = decider.decide("Test problem", options)
        assert "Test option" in result.reason

    def test_decide_preserves_alternatives(self, decider):
        options = [
            DecisionOption(option_id="a", description="A", confidence=0.9),
            DecisionOption(option_id="b", description="B", confidence=0.5),
        ]
        result = decider.decide("Test", options)
        assert len(result.alternatives) == 2

    def test_decide_with_confidence_override(self, decider):
        options = [DecisionOption(option_id="opt1", description="Test", confidence=0.5)]
        conf = ConfidenceScore(score=0.75, level="MEDIUM", factors={})
        result = decider.decide("Test", options, confidence=conf)
        assert result.confidence == 0.75

    def test_decide_respects_risk_level(self, decider):
        options = [DecisionOption(option_id="opt1", description="Test", confidence=0.8)]
        result = decider.decide("Test", options, risk_level="R3")
        assert result.risk == "R3"

    def test_decide_evidence_weighting_matters(self, decider):
        opt_no_ev = DecisionOption(option_id="no_ev", description="No evidence", confidence=0.8)
        opt_with_ev = DecisionOption(option_id="with_ev", description="Three evidence items", evidence=["a","b","c"], confidence=0.8)
        result = decider.decide("Test", [opt_no_ev, opt_with_ev])
        assert result.selected_option == "with_ev"
