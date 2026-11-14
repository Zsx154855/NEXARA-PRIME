"""Experience Store — persists mission execution outcomes for feedback loop.

Stores mission experiences (intent, contract, result, score, lessons)
for the Chief Brain Feedback Loop. Built on MemoryController read interface.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, TYPE_CHECKING

from nexara_prime.models import now_iso, new_id

if TYPE_CHECKING:
    from nexara_prime.brain.memory_controller import MemoryController


@dataclass(frozen=True)
class MissionExperience:
    """Immutable record of a completed mission."""
    experience_id: str
    mission_id: str
    objective: str
    risk_level: str
    adapter: str
    model: str
    status: str  # success|partial|failed|blocked
    score: float = 0.0
    lessons: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)


@dataclass(frozen=True)
class ExperienceStoreStats:
    """Aggregate statistics from experience store."""
    total_experiences: int
    success_rate: float
    avg_score: float
    by_risk_level: dict[str, int]
    by_adapter: dict[str, int]
    recent_lessons: list[str]


class ExperienceStore:
    """Persistent store for mission execution experiences.

    Each completed mission produces a MissionExperience record.
    The feedback loop queries these records to improve future
    planning, risk assessment, and adapter selection.
    """

    def __init__(
        self,
        memory_controller: MemoryController | None = None,
        *,
        evidence_validator: Callable[[str, str], bool] | None = None,
        evidence_store: Any | None = None,
        outcome_validator: Callable[[str, str], bool] | None = None,
    ) -> None:
        self._mc = memory_controller
        self._evidence_store = evidence_store
        # Must be a trusted, independent Mission/Contract acceptance authority,
        # NOT an agent-provided status, score, or evidence-integrity check.
        self._outcome_validator = outcome_validator
        self._evidence_validator = evidence_validator
        if self._evidence_validator is None and evidence_store is not None:
            def _canonical_evidence_check(mission_id: str, evidence_id: str) -> bool:
                try:
                    return (
                        evidence_store.is_preverified_and_integrity_bound(evidence_id) is True
                        and evidence_store.get_by_id(evidence_id).mission_id == mission_id
                    )
                except (KeyError, ValueError, RuntimeError, AttributeError):
                    return False
            self._evidence_validator = _canonical_evidence_check
        self._experiences: dict[str, MissionExperience] = {}
        # Persisted records must always be read from the canonical memory
        # layer, so a stale local cache cannot resurrect an invalidated record.
        self._persisted_ids: set[str] = set()

    def _canonical_business_outcome_verified(
        self, mission_id: str, evidence_id: str,
    ) -> bool:
        """Read existing Mission/Evidence/Receipt authorities; never create new state.

        Canonical success requires a terminal approved Mission with acceptance
        criteria, evaluation, receipt chain, verification evidence, independently
        issued reviewer/auditor verdicts, AND a trusted business outcome check.
        The injected outcome_validator is the integration seam to the existing
        independent business-acceptance runner. Without it, fail closed.
        """
        if self._evidence_store is None or self._outcome_validator is None:
            return False
        try:
            envelope = self._evidence_store.store.get_record_envelope(mission_id)
            if (
                not envelope
                or envelope.get("record_type") != "mission"
                or envelope.get("record_id") != mission_id
                or envelope.get("mission_id") != mission_id
            ):
                return False
            mission = envelope.get("payload")
            if not isinstance(mission, dict):
                return False
            result = mission.get("result")
            contract = mission.get("contract")
            spec = mission.get("spec")
            if (
                mission.get("mission_id") != mission_id
                or mission.get("state") != "Completed"
                or not isinstance(result, dict)
                or not isinstance(contract, dict)
                or contract.get("mission_id") != mission_id
                or contract.get("status") != "approved"
                or not isinstance(spec, dict)
                or spec.get("mission_id") != mission_id
                or not isinstance(contract.get("acceptance_criteria"), list)
                or not contract["acceptance_criteria"]
                or not result.get("evaluation_id")
                or result.get("evaluation_passed") is not True
                or result.get("verification_evidence_id") != evidence_id
            ):
                return False

            # Do not let an injected legacy evidence_validator bypass the
            # canonical evidence verification-status / origin-chain checks.
            if self._evidence_store.is_preverified_and_integrity_bound(evidence_id) is not True:
                return False
            verification = self._evidence_store.get_by_id(evidence_id)
            if (
                verification.mission_id != mission_id
                or verification.kind != "verification_report"
                or verification.actor != "reviewer"
            ):
                return False
            if self._evidence_store.receipt_status(mission_id).get("status") != "present":
                return False

            for field, kind, actor in (
                ("reviewer_evidence_id", "reviewer_verdict", "reviewer"),
                ("auditor_evidence_id", "auditor_verdict", "auditor"),
            ):
                verdict_id = result.get(field)
                if not isinstance(verdict_id, str) or not verdict_id:
                    return False
                if self._evidence_store.is_preverified_and_integrity_bound(verdict_id) is not True:
                    return False
                artifact = self._evidence_store.get_by_id(verdict_id)
                if artifact.mission_id != mission_id or artifact.kind != kind or artifact.actor != actor:
                    return False
                verdict = json.loads(artifact.content)
                if (
                    not isinstance(verdict, dict)
                    or verdict.get("mission_id") != mission_id
                    or verdict.get("actor") != actor
                    or verdict.get("passed") is not True
                ):
                    return False

            # This must validate actual acceptance results, not just the
            # structurally valid completion chain above.
            return self._outcome_validator(mission_id, evidence_id) is True
        except (KeyError, TypeError, ValueError, RuntimeError, AttributeError, OSError):
            return False

    def record(
        self,
        mission_id: str,
        objective: str,
        risk_level: str,
        adapter: str,
        model: str,
        status: str,
        *,
        score: float = 0.0,
        lessons: list[str] | None = None,
        evidence_refs: list[str] | None = None,
    ) -> MissionExperience:
        """Record a completed mission experience.

        Returns:
            MissionExperience record.
        """
        exp_id = new_id("exp")
        exp = MissionExperience(
            experience_id=exp_id,
            mission_id=mission_id,
            objective=objective,
            risk_level=risk_level,
            adapter=adapter,
            model=model,
            status=status,
            score=score,
            lessons=lessons or [],
            evidence_refs=evidence_refs or [],
        )
        refs = list(exp.evidence_refs)
        # Canonical success admission applies even to an in-memory instance.
        # The pre-existing callback-only mode remains a legacy compatibility
        # surface; it is NOT an independent business outcome authority.
        if status == "success" and self._evidence_store is not None:
            if (
                not refs
                or not isinstance(refs[0], str)
                or self._evidence_validator is None
                or self._evidence_validator(mission_id, refs[0]) is not True
            ):
                raise ValueError("experience_verified_evidence_required")
            if not self._canonical_business_outcome_verified(mission_id, refs[0]):
                raise ValueError("mission_outcome_not_independently_verified")
        if self._mc is not None:
            if (
                not refs
                or not isinstance(refs[0], str)
                or self._evidence_validator is None
                or self._evidence_validator(mission_id, refs[0]) is not True
            ):
                raise ValueError("experience_verified_evidence_required")
            self._mc.commit(
                mission_id=mission_id,
                key=f"mission_experience:{exp_id}",
                content=json.dumps(asdict(exp), sort_keys=True),
                kind="experience",
                evidence_id=refs[0],
                confidence=max(0.0, min(1.0, score)),
            )
            self._persisted_ids.add(exp_id)
        self._experiences[exp_id] = exp
        return exp

    def get(self, experience_id: str) -> MissionExperience | None:
        return next((e for e in self.list_all() if e.experience_id == experience_id), None)

    def get_by_mission(self, mission_id: str) -> list[MissionExperience]:
        return [e for e in self.list_all() if e.mission_id == mission_id]

    def list_all(self) -> list[MissionExperience]:
        if self._mc is None:
            return list(self._experiences.values())
        # MemoryController.rank_retrieve filters non-active records; never
        # resurrect superseded or invalidated knowledge from local caches.
        records = self._mc.rank_retrieve(
            query="mission_experience:", top_k=10000,
            layers=["semantic"], min_confidence=0.0,
        )
        active: dict[str, MissionExperience] = {}
        for record in records:
            if (
                record.get("kind") != "experience"
                or record.get("status") != "active"
                or not str(record.get("key", "")).startswith("mission_experience:")
            ):
                continue
            try:
                parsed = json.loads(str(record["content"]))
                exp = MissionExperience(**parsed)
            except (TypeError, ValueError, KeyError):
                continue
            # MemoryController only accepts evidence-bound experience writes.
            if (
                exp.evidence_refs
                and exp.evidence_refs[0] == record.get("evidence_id")
                and self._evidence_validator is not None
                and self._evidence_validator(exp.mission_id, exp.evidence_refs[0]) is True
            ):
                # Existing canonical success records without a current
                # independent business outcome are quarantined from learning.
                # Legacy test-only validators are preserved for old callers;
                # their results must not be considered production assurance.
                if (
                    exp.status != "success"
                    or self._evidence_store is None
                    or self._canonical_business_outcome_verified(exp.mission_id, exp.evidence_refs[0])
                ):
                    active[exp.experience_id] = exp
        return list(active.values())

    def list_by_risk(self, risk_level: str) -> list[MissionExperience]:
        return [e for e in self.list_all() if e.risk_level == risk_level]

    def list_by_status(self, status: str) -> list[MissionExperience]:
        return [e for e in self.list_all() if e.status == status]

    def list_by_adapter(self, adapter: str) -> list[MissionExperience]:
        return [e for e in self.list_all() if e.adapter == adapter]

    def stats(self) -> ExperienceStoreStats:
        all_exp = self.list_all()
        total = len(all_exp)
        if total == 0:
            return ExperienceStoreStats(
                total_experiences=0, success_rate=0.0, avg_score=0.0,
                by_risk_level={}, by_adapter={}, recent_lessons=[],
            )

        successes = sum(1 for e in all_exp if e.status == "success")
        avg_score = sum(e.score for e in all_exp) / total

        by_risk: dict[str, int] = {}
        by_adapter: dict[str, int] = {}
        for e in all_exp:
            by_risk[e.risk_level] = by_risk.get(e.risk_level, 0) + 1
            by_adapter[e.adapter] = by_adapter.get(e.adapter, 0) + 1

        recent = sorted(all_exp, key=lambda e: e.created_at, reverse=True)[:10]
        recent_lessons = [l for e in recent for l in e.lessons]

        return ExperienceStoreStats(
            total_experiences=total,
            success_rate=round(successes / total, 4),
            avg_score=round(avg_score, 4),
            by_risk_level=by_risk,
            by_adapter=by_adapter,
            recent_lessons=recent_lessons[:20],
        )

    def __len__(self) -> int:
        return len(self.list_all())
