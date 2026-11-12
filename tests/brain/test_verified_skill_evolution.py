import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("verified_skill_evolution", ROOT / "src/nexara_prime/brain/verified_skill_evolution.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
SkillCandidate, Trial, VerifiedSkillEvolution = module.SkillCandidate, module.Trial, module.VerifiedSkillEvolution


def candidate(**overrides):
    data = dict(skill_id="candidate", version="v2", author_id="engineer",
                baseline_version="v1", rollback_ref="sha:a1", development_task_ids=frozenset({"dev-1"}))
    data.update(overrides)
    return SkillCandidate(**data)


def trials(turns=4, ctrl=6, tokens=80, ctrl_tokens=100, count=3):
    t = []
    for n in range(count):
        for variant, steps, tok in (("treatment", turns, tokens), ("control", ctrl, ctrl_tokens)):
            t.append(Trial(f"holdout-{n}", variant, True, steps, f"ev-{n}-{variant}",
                           "independent-qa", tok))
    return tuple(t)


def gate():
    return VerifiedSkillEvolution(lambda x: x.evidence_id.startswith("ev-"))


def test_valid_independent_holdout_only_eligible_for_review():
    x = gate().assess(candidate(), trials())
    assert x.status == "ELIGIBLE_FOR_REVIEW"
    assert not x.authorization_granted and not x.active_version_changed


def test_no_evidence_store_cannot_verify():
    assert VerifiedSkillEvolution().assess(candidate(), trials()).status == "NOT_VERIFIED"


def test_one_pair_not_valid_transfer():
    assert gate().assess(candidate(), trials(count=1)).status == "NOT_VERIFIED"


def test_prior_treatment_46_vs_control_35_does_not_pass():
    assert gate().assess(candidate(), trials(turns=46, ctrl=35)).status == "REJECTED"


def test_missing_token_data_not_interpreted_as_savings():
    assert gate().assess(candidate(), trials(tokens=None)).reason == "TOKEN_METRICS_UNKNOWN"


def test_equal_outcome_equal_cost_not_skill_evolution():
    assert gate().assess(candidate(), trials(turns=5, ctrl=5, tokens=100, ctrl_tokens=100)).status == "REJECTED"


def test_holdout_contamination_rejected():
    assert gate().assess(candidate(development_task_ids=frozenset({"holdout-0"})), trials()).reason == "HOLDOUT_LEAKAGE"


def test_self_review_rejected():
    bad = tuple(Trial(x.task_id, x.variant, x.passed, x.turns, x.evidence_id, "engineer", x.input_tokens)
                for x in trials())
    assert gate().assess(candidate(), bad).reason == "SELF_REVIEW"


def test_quality_regression_fails_even_if_fast():
    t = list(trials())
    x = t[0]
    t[0] = Trial(x.task_id, x.variant, False, 1, x.evidence_id, x.reviewer_id, 1)
    assert gate().assess(candidate(), tuple(t)).reason == "QUALITY_REGRESSION"


def test_unverified_evidence_rejected():
    assert VerifiedSkillEvolution(lambda _: False).assess(candidate(), trials()).status == "NOT_VERIFIED"


def test_missing_rollback_prevents_eligibility():
    assert gate().assess(candidate(rollback_ref=""), trials()).reason == "INCOMPLETE_CANDIDATE_OR_ROLLBACK"


def test_duplicate_trial_not_counted_twice():
    both = trials() + (trials()[0],)
    assert gate().assess(candidate(), both).reason == "DUPLICATE_TRIAL"
