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

    def test_constructor_goal_inherited(self):
        engine = DecisionEngine(goal="deploy", available_actions=["a"])
        d = engine.decide()
        assert d.input == "deploy"

    def test_none_goal_produces_none_string(self):
        engine = DecisionEngine(available_actions=["a"])
        d = engine.decide(goal=None)
        assert d.input == "None"

    def test_policy_key_with_none_value_skipped(self):
        engine = DecisionEngine(
            available_actions=["a"],
            policy={"mandatory_action": None, "forced_action": "fallback"},
        )
        d = engine.decide()
        assert d.selected_action == "fallback"

    def test_all_policy_keys_none_falls_to_first_available(self):
        engine = DecisionEngine(
            available_actions=["a"],
            policy={"mandatory_action": None, "forced_action": None, "action": None},
        )
        d = engine.decide()
        assert d.selected_action == "a"
        assert d.reason_code == "first_available"

    def test_unknown_mode_falls_back_to_normal_confidence(self):
        engine = DecisionEngine(available_actions=["a"], reasoning_mode="unknown_mode")
        d = engine.decide()
        assert d.confidence == 0.8

    def test_objective_plain_string(self):
        engine = DecisionEngine(available_actions=["a"])
        d = engine.decide(goal="just a string")
        assert d.input == "just a string"

    def test_objective_dict_without_objective_or_intent(self):
        engine = DecisionEngine(available_actions=["a"])
        d = engine.decide(goal={"key": "val"})
        assert d.input == str({"key": "val"})

    def test_objective_object_without_objective_attr_falls_back_to_str(self):
        class G:
            intent = "analyze"
        engine = DecisionEngine(available_actions=["a"])
        g = G()
        d = engine.decide(goal=g)
        assert d.input == str(g)

    def test_policy_mandated_with_empty_actions(self):
        engine = DecisionEngine(
            available_actions=[],
            policy={"mandatory_action": "forced"},
        )
        d = engine.decide()
        assert d.selected_action == "forced"
        assert d.reason_code == "policy_mandated"

    def test_available_actions_copy_isolation(self):
        original = ["a", "b"]
        engine = DecisionEngine(available_actions=original)
        d = engine.decide()
        d.available_actions.append("c")
        assert engine.available_actions == ["a", "b"]

    def test_decide_overrides_context(self):
        engine = DecisionEngine(context={"a": 1})
        d = engine.decide(context={"b": 2}, available_actions=["x"])
        assert d.context == {"b": 2}

    def test_decide_overrides_policy(self):
        engine = DecisionEngine(
            available_actions=["a"],
            policy={"mandatory_action": "old"},
        )
        d = engine.decide(policy={"mandatory_action": "new"})
        assert d.selected_action == "new"
