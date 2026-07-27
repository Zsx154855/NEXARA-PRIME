"""Tests: Self Check Validator — 5 checks."""

import pytest
from src.nexara_prime.brain.reasoning import SelfCheckValidator, ReasoningStep


@pytest.fixture
def checker():
    return SelfCheckValidator()


def make_step(step_id, step_type, output="", confidence=0.7, evidence_refs=None, depends_on=None):
    return ReasoningStep(
        step_id=step_id,
        step_type=step_type,
        output=output,
        confidence=confidence,
        evidence_refs=evidence_refs or [],
        depends_on=depends_on or [],
    )


class TestSelfCheck:
    """10 tests: all 5 checks, pass/fail scenarios."""

    def test_valid_chain_passes(self, checker):
        steps = [
            make_step("s1", "OBSERVE", "facts", evidence_refs=["ev1", "ev2", "ev3", "ev4", "ev5"]),
            make_step("s2", "CLASSIFY", "type", depends_on=["s1"]),
            make_step("s3", "INFER", "conclusion", confidence=0.6, evidence_refs=["ev1", "ev2", "ev3"], depends_on=["s2"]),
            make_step("s4", "SYNTHESIZE", "final", confidence=0.6, evidence_refs=["ev1", "ev2", "ev3"], depends_on=["s3"]),
        ]
        result = checker.validate(steps)
        assert result.overall_pass

    def test_missing_evidence_fails(self, checker):
        steps = [
            make_step("s1", "OBSERVE", "facts"),
            make_step("s2", "INFER", "conclusion"),  # no evidence
        ]
        result = checker.validate(steps)
        assert not result.overall_pass

    def test_orphan_dependency_fails(self, checker):
        steps = [
            make_step("s1", "OBSERVE", depends_on=["s_nonexistent"]),
        ]
        result = checker.validate(steps)
        assert not result.overall_pass

    def test_no_cycle_passes(self, checker):
        steps = [
            make_step("s1", "OBSERVE", depends_on=[], evidence_refs=["ev1", "ev2", "ev3"]),
            make_step("s2", "INFER", depends_on=["s1"], confidence=0.5, evidence_refs=["ev1", "ev2"]),
        ]
        result = checker.validate(steps)
        assert result.overall_pass

    def test_cycle_detected(self, checker):
        steps = [
            make_step("s1", "INFER", depends_on=["s2"]),
            make_step("s2", "INFER", depends_on=["s1"]),
        ]
        result = checker.validate(steps)
        assert not result.overall_pass

    def test_overconfident_flagged(self, checker):
        steps = [
            make_step("s1", "INFER", confidence=0.95),  # no evidence → evidence_strength=0 → gap=0.95
        ]
        result = checker.validate(steps)
        assert not result.overall_pass

    def test_contradiction_detected(self, checker):
        steps = [
            make_step("s1", "INFER", output="yes"),
            make_step("s2", "INFER", output="no"),
        ]
        result = checker.validate(steps)
        assert not result.overall_pass

    def test_checks_total_is_5(self, checker):
        steps = [make_step("s1", "OBSERVE", evidence_refs=["ev1"])]
        result = checker.validate(steps)
        assert result.checks_total == 5

    def test_failures_list_populated(self, checker):
        steps = [make_step("s1", "INFER")]  # no evidence, overconfident
        result = checker.validate(steps)
        assert len(result.failures) > 0

    def test_remediation_suggested(self, checker):
        steps = [make_step("s1", "INFER")]  # missing evidence
        result = checker.validate(steps)
        assert len(result.remediation) > 0
