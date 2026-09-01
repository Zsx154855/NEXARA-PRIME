"""Tests for intelligence.reflection — Reflection contract + ReflectionLoop."""
from __future__ import annotations

import pytest

from nexara_prime.intelligence.evaluator.contracts import Evaluation
from nexara_prime.intelligence.reflection.contracts import Reflection
from nexara_prime.intelligence.reflection.reflection_loop import ReflectionLoop


class TestReflection:
    def test_defaults(self):
        r = Reflection()
        assert r.experience_id.startswith("exp_")
        assert r.evaluation is None
        assert r.insight == ""
        assert r.memory_update_policy == "retain"


class TestReflectionLoop:
    def setup_method(self):
        self.loop = ReflectionLoop()

    def test_success_retains_strategy(self):
        ev = Evaluation(success_score=1.0, mission_id="m1")
        r = self.loop.reflect(ev)
        assert r.insight == "keep strategy"
        assert r.memory_update_policy == "retain"
        assert r.evaluation is ev

    def test_failure_adjusts_strategy(self):
        ev = Evaluation(success_score=0.0, mission_id="m2")
        r = self.loop.reflect(ev)
        assert r.insight == "adjust strategy"
        assert r.memory_update_policy == "update_memory"

    def test_partial_success_adjusts(self):
        ev = Evaluation(success_score=0.5)
        r = self.loop.reflect(ev)
        assert r.memory_update_policy == "update_memory"

    def test_reflection_has_unique_id(self):
        ev = Evaluation(success_score=1.0)
        r1 = self.loop.reflect(ev)
        r2 = self.loop.reflect(ev)
        assert r1.experience_id != r2.experience_id

    def test_threshold_edge_just_below_one(self):
        ev = Evaluation(success_score=0.999)
        r = self.loop.reflect(ev)
        assert r.memory_update_policy == "update_memory"

    def test_above_one_retains(self):
        ev = Evaluation(success_score=1.5)
        r = self.loop.reflect(ev)
        assert r.memory_update_policy == "retain"

    def test_negative_score_adjusts(self):
        ev = Evaluation(success_score=-1.0)
        r = self.loop.reflect(ev)
        assert r.memory_update_policy == "update_memory"

    def test_reflection_with_explicit_fields(self):
        ev = Evaluation(success_score=0.5, mission_id="m1")
        r = Reflection(
            evaluation=ev,
            insight="custom insight",
            memory_update_policy="custom_policy",
        )
        assert r.insight == "custom insight"
        assert r.memory_update_policy == "custom_policy"
        assert r.evaluation is ev
