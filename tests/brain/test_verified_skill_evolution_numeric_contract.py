"""Adversarial numeric-input tests for the MCRE skill-evolution proposal gate.

The verifier is deliberately permissive to isolate input validation. These are
not real EvidenceStore receipts or proof of authentic independent review.
"""
from dataclasses import replace

import pytest

from nexara_prime.brain.verified_skill_evolution import (
    SkillCandidate,
    Trial,
    VerifiedSkillEvolution,
)


def _candidate():
    return SkillCandidate("s1", "v2", "agent-A", "v1", "rollback-ref", frozenset())


def _trials():
    result = []
    for i in range(3):
        result.append(Trial(f"holdout-{i}", "treatment", True, 4, f"ev-{i}-t", "QA", 80, 0.001))
        result.append(Trial(f"holdout-{i}", "control", True, 6, f"ev-{i}-c", "QA", 100, 0.002))
    return result


@pytest.mark.parametrize("field,value", [
    ("passed", 1),
    ("turns", True),
    ("turns", 2.0),
    ("input_tokens", True),
    ("input_tokens", 1.0),
    ("cost_usd", float("nan")),
    ("cost_usd", float("inf")),
])
def test_invalid_positive_data_not_evolution_eligible(field, value):
    trials = _trials()
    trials[0] = replace(trials[0], **{field: value})
    result = VerifiedSkillEvolution(lambda _: True).assess(_candidate(), tuple(trials))
    assert result.status == "NOT_VERIFIED", (field, value, result)


def test_valid_paired_trial_remains_advisory():
    result = VerifiedSkillEvolution(lambda _: True).assess(_candidate(), tuple(_trials()))
    assert result.status == "ELIGIBLE_FOR_REVIEW"
    assert not result.authorization_granted and not result.active_version_changed


@pytest.mark.parametrize("value", [True, 2.0])
def test_holdout_pair_threshold_rejects_nonstrict_integer(value):
    with pytest.raises(ValueError):
        VerifiedSkillEvolution(lambda _: True, min_holdout_pairs=value)


def test_nonfinite_control_cost_cannot_elevate_candidate():
    trials = _trials()
    trials[1] = replace(trials[1], cost_usd=float("nan"))
    result = VerifiedSkillEvolution(lambda _: True).assess(_candidate(), tuple(trials))
    assert result.status == "NOT_VERIFIED", result
