"""Tests for intelligence.decision — contracts + DecisionEngine."""
from __future__ import annotations

import pytest

from nexara_prime.intelligence.decision.contracts import (
    Decision,
    DecisionTrace,
    ReasoningMode,
)
from nexara_prime.intelligence.decision.decision_engine import DecisionEngine


class TestReasoningMode:
    def test_five_modes(self):
        assert len(ReasoningMode) == 5

    def test_values(self):
        vals = {m.value for m in ReasoningMode}
        assert vals == {"normal", "fast", "deep", "recovery", "cost_optimized"}


class TestDecision:
    def test_defaults(self):
        d = Decision()
        assert d.input is None
        assert d.context == {}
        assert d.available_actions == []
        assert d.selected_action is None
        assert d.confidence == 0.0


class TestDecisionTrace:
    def test_defaults(self):
        t = DecisionTrace()
        assert t.decision_summary == ""
        assert t.reason_code == ""
        assert t.policy_reference == ""


class TestDecisionEngine:
    def test_first_available_action(self):
        engine = DecisionEngine(available_actions=["a", "b"])
        d = engine.decide(goal="test")
        assert d.selected_action == "a"
        assert d.reason_code == "first_available"
        assert d.confidence == 0.8

    def test_policy_mandated_action(self):
        engine = DecisionEngine(
            available_actions=["a", "b"],
            policy={"mandatory_action": "b", "policy_reference": "P1"},
        )
        d = engine.decide(goal="test")
        assert d.selected_action == "b"
        assert d.reason_code == "policy_mandated"
        assert d.policy_reference == "P1"

    def test_forced_action_key(self):
        engine = DecisionEngine(
            available_actions=["a"],
            policy={"forced_action": "x"},
        )
        d = engine.decide()
        assert d.selected_action == "x"
        assert d.reason_code == "policy_mandated"

    def test_action_key_fallback(self):
        engine = DecisionEngine(
            available_actions=["a"],
            policy={"action": "y"},
        )
        d = engine.decide()
        assert d.selected_action == "y"

    def test_mandatory_key_priority(self):
        engine = DecisionEngine(
            available_actions=["a"],
            policy={"mandatory_action": "m", "forced_action": "f", "action": "x"},
        )
        d = engine.decide()
        assert d.selected_action == "m"

    def test_no_actions_no_policy(self):
        engine = DecisionEngine()
        d = engine.decide(goal="test")
        assert d.selected_action is None
        assert d.reason_code == "no_available_action"
        assert d.confidence == 0.0

    def test_confidence_by_mode(self):
        for mode, expected in [
            (ReasoningMode.NORMAL, 0.8),
            (ReasoningMode.FAST, 0.6),
            (ReasoningMode.DEEP, 0.9),
            (ReasoningMode.RECOVERY, 0.5),
            (ReasoningMode.COST_OPTIMIZED, 0.7),
        ]:
            engine = DecisionEngine(available_actions=["a"], reasoning_mode=mode)
            d = engine.decide()
            assert d.confidence == expected

    def test_override_mode_at_decide_time(self):
        engine = DecisionEngine(available_actions=["a"], reasoning_mode=ReasoningMode.NORMAL)
        d = engine.decide(reasoning_mode=ReasoningMode.DEEP)
        assert d.confidence == 0.9

    def test_goal_as_dict(self):
        engine = DecisionEngine(available_actions=["a"])
        d = engine.decide(goal={"objective": "fix bug"})
        assert d.input == "fix bug"

    def test_goal_as_object(self):
        class G:
            objective = "deploy"
        engine = DecisionEngine(available_actions=["a"])
        d = engine.decide(goal=G())
        assert d.input == "deploy"

    def test_goal_dict_intent_fallback(self):
        engine = DecisionEngine(available_actions=["a"])
        d = engine.decide(goal={"intent": "analyze"})
        assert d.input == "analyze"

    def test_context_preserved(self):
        engine = DecisionEngine(available_actions=["a"], context={"key": "val"})
        d = engine.decide()
        assert d.context == {"key": "val"}

    def test_policy_reference_from_name(self):
        engine = DecisionEngine(
            available_actions=["a"],
            policy={"name": "safety_first"},
        )
        d = engine.decide()
        assert d.policy_reference == "safety_first"

    def test_decide_overrides_actions(self):
        engine = DecisionEngine(available_actions=["a"])
        d = engine.decide(available_actions=["x", "y"])
        assert d.selected_action == "x"
        assert d.available_actions == ["x", "y"]
