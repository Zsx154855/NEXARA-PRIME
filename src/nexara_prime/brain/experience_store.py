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
    ) -> None:
        self._mc = memory_controller
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
        if self._mc is not None:
            refs = list(exp.evidence_refs)
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
