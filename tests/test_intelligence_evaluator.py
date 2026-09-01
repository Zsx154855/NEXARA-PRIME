"""Tests for intelligence.evaluator — Evaluation contract + EvaluationEngine."""
from __future__ import annotations

import pytest

from nexara_prime.intelligence.evaluator.contracts import Evaluation
from nexara_prime.intelligence.evaluator.evaluator import EvaluationEngine


class TestEvaluation:
    def test_defaults(self):
        e = Evaluation()
        assert e.mission_id == ""
        assert e.quality_score == 0.0
        assert e.success_score == 0.0
        assert e.recommendation == "retry"


class TestEvaluationEngine:
    def setup_method(self):
        self.engine = EvaluationEngine()

    def test_completed_mission_high_evidence(self):
        result = {
            "mission_id": "m1",
            "current_state": "Completed",
            "evidence_count": 12,
            "cost_score": 0.8,
            "latency_ms": 500,
            "recovery_count": 1,
        }
        e = self.engine.evaluate(result)
        assert e.mission_id == "m1"
        assert e.quality_score == 0.9
        assert e.success_score == 1.0
        assert e.cost_score == 0.8
        assert e.latency_ms == 500
        assert e.failure_count == 0
        assert e.recovery_count == 1
        assert e.recommendation == "continue"

    def test_completed_mission_medium_evidence(self):
        result = {"current_state": "Completed", "evidence_count": 7}
        e = self.engine.evaluate(result)
        assert e.quality_score == 0.7
        assert e.success_score == 1.0
        assert e.recommendation == "continue"

    def test_completed_mission_low_evidence(self):
        result = {"current_state": "Completed", "evidence_count": 3}
        e = self.engine.evaluate(result)
        assert e.quality_score == 0.4
        assert e.success_score == 1.0

    def test_failed_mission(self):
        result = {"current_state": "Failed", "evidence_count": 0}
        e = self.engine.evaluate(result)
        assert e.success_score == 0.0
        assert e.failure_count == 1
        assert e.recommendation == "retry"

    def test_missing_fields_default(self):
        e = self.engine.evaluate({})
        assert e.mission_id == ""
        assert e.quality_score == 0.4
        assert e.success_score == 0.0
        assert e.cost_score == 0.0
        assert e.latency_ms == 0
        assert e.recommendation == "retry"

    def test_evidence_boundary_at_5(self):
        e = self.engine.evaluate({"evidence_count": 5, "current_state": "Completed"})
        assert e.quality_score == 0.7

    def test_evidence_boundary_at_10(self):
        e = self.engine.evaluate({"evidence_count": 10, "current_state": "Completed"})
        assert e.quality_score == 0.9

    def test_evidence_boundary_at_4(self):
        e = self.engine.evaluate({"evidence_count": 4, "current_state": "Completed"})
        assert e.quality_score == 0.4

    def test_running_state_treated_as_failure(self):
        e = self.engine.evaluate({"current_state": "Running", "evidence_count": 10})
        assert e.success_score == 0.0
        assert e.failure_count == 1
        assert e.recommendation == "retry"

    def test_pending_state_treated_as_failure(self):
        e = self.engine.evaluate({"current_state": "Pending"})
        assert e.success_score == 0.0

    def test_case_sensitive_state(self):
        e = self.engine.evaluate({"current_state": "completed", "evidence_count": 10})
        assert e.success_score == 0.0

    def test_evidence_string_coercion(self):
        e = self.engine.evaluate({"current_state": "Completed", "evidence_count": "12"})
        assert e.quality_score == 0.9

    def test_evidence_boundary_at_9(self):
        e = self.engine.evaluate({"current_state": "Completed", "evidence_count": 9})
        assert e.quality_score == 0.7

    def test_negative_evidence_treated_as_low(self):
        e = self.engine.evaluate({"current_state": "Completed", "evidence_count": -1})
        assert e.quality_score == 0.4

    def test_cost_score_string_coercion(self):
        e = self.engine.evaluate({"current_state": "Completed", "cost_score": "0.5"})
        assert e.cost_score == 0.5

    def test_mission_id_non_str_coerced(self):
        e = self.engine.evaluate({"mission_id": 42})
        assert e.mission_id == "42"

    def test_mission_id_none_becomes_empty_string(self):
        e = self.engine.evaluate({})
        assert e.mission_id == ""

    def test_recovery_count_default_zero(self):
        e = self.engine.evaluate({"current_state": "Completed"})
        assert e.recovery_count == 0
