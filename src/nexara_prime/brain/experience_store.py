"""Experience Store — persists mission execution outcomes for feedback loop.

Stores mission experiences (intent, contract, result, score, lessons)
for the Chief Brain Feedback Loop. Built on MemoryController read interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

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

    def __init__(self, memory_controller: MemoryController | None = None) -> None:
        self._mc = memory_controller
        self._experiences: dict[str, MissionExperience] = {}

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
        self._experiences[exp_id] = exp
        return exp

    def get(self, experience_id: str) -> MissionExperience | None:
        return self._experiences.get(experience_id)

    def get_by_mission(self, mission_id: str) -> list[MissionExperience]:
        return [e for e in self._experiences.values() if e.mission_id == mission_id]

    def list_all(self) -> list[MissionExperience]:
        return list(self._experiences.values())

    def list_by_risk(self, risk_level: str) -> list[MissionExperience]:
        return [e for e in self._experiences.values() if e.risk_level == risk_level]

    def list_by_status(self, status: str) -> list[MissionExperience]:
        return [e for e in self._experiences.values() if e.status == status]

    def list_by_adapter(self, adapter: str) -> list[MissionExperience]:
        return [e for e in self._experiences.values() if e.adapter == adapter]

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
        return len(self._experiences)
