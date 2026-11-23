"""Advisory gate for evidence-backed skill evolution: never activates a skill.

Candidates must beat a *paired unseen* control on independently reviewed
outcomes. The evidence verifier must compare ALL trial fields with immutable
EvidenceStore receipts, not merely check that an ID exists. Promotion/rollback
authority remains with the existing AutonomousBoundary and Runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Callable


@dataclass(frozen=True)
class SkillCandidate:
    skill_id: str
    version: str
    author_id: str
    baseline_version: str
    rollback_ref: str
    development_task_ids: frozenset[str]


@dataclass(frozen=True)
class Trial:
    task_id: str
    variant: str  # treatment | control
    passed: bool
    turns: int
    evidence_id: str
    reviewer_id: str
    input_tokens: int | None = None
    cost_usd: float | None = None


@dataclass(frozen=True)
class EvolutionAdvice:
    status: str  # NOT_VERIFIED | REJECTED | ELIGIBLE_FOR_REVIEW
    reason: str
    tested_tasks: int
    authorization_granted: bool = False
    active_version_changed: bool = False


class VerifiedSkillEvolution:
    name = "verified_skill_evolution"

    def __init__(self, verify_evidence: Callable[[Trial], bool] | None = None,
                 min_holdout_pairs: int = 3) -> None:
        if type(min_holdout_pairs) is not int or min_holdout_pairs < 2:
            raise ValueError("at least two holdout pairs required")
        self._verify_evidence = verify_evidence
        self._min_pairs = min_holdout_pairs

    def assess(self, candidate: SkillCandidate, trials: tuple[Trial, ...]) -> EvolutionAdvice:
        def verdict(status: str, reason: str, count: int = 0) -> EvolutionAdvice:
            return EvolutionAdvice(status, reason, count)

        if not all([candidate.skill_id, candidate.version, candidate.author_id,
                    candidate.baseline_version, candidate.rollback_ref]):
            return verdict("NOT_VERIFIED", "INCOMPLETE_CANDIDATE_OR_ROLLBACK")
        if candidate.version == candidate.baseline_version:
            return verdict("NOT_VERIFIED", "SAME_VERSION")
        if self._verify_evidence is None:
            return verdict("NOT_VERIFIED", "EVIDENCESTORE_UNAVAILABLE")
        groups: dict[str, dict[str, Trial]] = {}
        for trial in trials:
            if (not isinstance(trial.task_id, str) or not trial.task_id
                    or trial.variant not in ("treatment", "control")
                    or not isinstance(trial.evidence_id, str) or not trial.evidence_id
                    or not isinstance(trial.reviewer_id, str) or not trial.reviewer_id
                    or type(trial.passed) is not bool
                    or type(trial.turns) is not int or trial.turns < 0
                    or (trial.input_tokens is not None and
                        (type(trial.input_tokens) is not int or trial.input_tokens < 0))
                    or (trial.cost_usd is not None and
                        (type(trial.cost_usd) not in (int, float)
                         or not isfinite(trial.cost_usd) or trial.cost_usd < 0))):
                return verdict("NOT_VERIFIED", "INVALID_TRIAL")
            if trial.task_id in candidate.development_task_ids:
                return verdict("NOT_VERIFIED", "HOLDOUT_LEAKAGE")
            if trial.reviewer_id == candidate.author_id:
                return verdict("NOT_VERIFIED", "SELF_REVIEW")
            pair = groups.setdefault(trial.task_id, {})
            if trial.variant in pair:
                return verdict("NOT_VERIFIED", "DUPLICATE_TRIAL")
            try:
                if self._verify_evidence(trial) is not True:
                    return verdict("NOT_VERIFIED", "UNVERIFIED_TRIAL_EVIDENCE")
            except Exception:
                return verdict("NOT_VERIFIED", "EVIDENCE_LOOKUP_FAILED")
            pair[trial.variant] = trial
        if len(groups) < self._min_pairs or any(set(x) != {"treatment", "control"} for x in groups.values()):
            return verdict("NOT_VERIFIED", "INSUFFICIENT_PAIRED_HOLDOUT", len(groups))
        pairs = list(groups.values())
        # A verified feature regression is disqualifying even if average efficiency improves.
        if any(p["control"].passed and not p["treatment"].passed for p in pairs):
            return verdict("REJECTED", "QUALITY_REGRESSION", len(pairs))
        if not all(p["treatment"].passed for p in pairs):
            return verdict("REJECTED", "TREATMENT_NOT_ALL_PASS", len(pairs))
        if any(p["treatment"].turns > p["control"].turns for p in pairs):
            return verdict("REJECTED", "NO_EFFICIENCY_DOMINANCE", len(pairs))
        # Missing token/cost reports cannot be treated as zero or claim financial savings.
        if any(p["treatment"].input_tokens is None or p["control"].input_tokens is None
               for p in pairs):
            return verdict("NOT_VERIFIED", "TOKEN_METRICS_UNKNOWN", len(pairs))
        if any(p["treatment"].input_tokens > p["control"].input_tokens for p in pairs):
            return verdict("REJECTED", "TOKEN_REGRESSION", len(pairs))
        if any(p["treatment"].cost_usd is None or p["control"].cost_usd is None for p in pairs):
            return verdict("NOT_VERIFIED", "COST_METRICS_UNKNOWN", len(pairs))
        if any(p["treatment"].cost_usd > p["control"].cost_usd for p in pairs):
            return verdict("REJECTED", "COST_REGRESSION", len(pairs))
        saved = any(p["treatment"].turns < p["control"].turns
                    or p["treatment"].input_tokens < p["control"].input_tokens for p in pairs)
        if not saved:
            return verdict("REJECTED", "NO_MEASURED_GAIN", len(pairs))
        return verdict("ELIGIBLE_FOR_REVIEW", "INDEPENDENT_HOLDOUT_GAIN_NOT_AUTHORIZATION", len(pairs))
