"""Memory Governance — rules for experience memory lifecycle.

Controls retention, decay, pruning, and quality thresholds for
experience memory. Ensures the feedback loop uses high-quality
experiences and discards noise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nexara_prime.brain.experience_store import MissionExperience


@dataclass(frozen=True)
class RetentionPolicy:
    """Policy for retaining or pruning experience records."""
    min_score: float = 0.3
    max_age_days: int = 90
    min_lessons: int = 0
    keep_failures: bool = True


@dataclass
class GovernanceDecision:
    """Decision on whether to retain an experience."""
    experience_id: str
    retain: bool
    reason: str
    action: str  # keep|archive|prune
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryGovernance:
    """Governs experience memory lifecycle.

    Rules:
      - Low-score experiences are candidates for pruning.
      - Old experiences (>90 days) are archived.
      - Failure experiences are always retained (learning value).
      - High-score experiences are promoted for recall priority.
    """

    def __init__(self, policy: RetentionPolicy | None = None) -> None:
        self._policy = policy or RetentionPolicy()
        self._decisions: list[GovernanceDecision] = []

    def evaluate(self, experience: MissionExperience) -> GovernanceDecision:
        """Evaluate whether an experience should be retained.

        Returns:
            GovernanceDecision with retain/archive/prune action.
        """
        # Always keep failures
        if experience.status in ("failed", "blocked") and self._policy.keep_failures:
            d = GovernanceDecision(
                experience_id=experience.experience_id,
                retain=True,
                reason="failure_preserved_for_learning",
                action="keep",
            )
            self._decisions.append(d)
            return d

        # Prune very low scores
        if experience.score < self._policy.min_score:
            d = GovernanceDecision(
                experience_id=experience.experience_id,
                retain=False,
                reason=f"score_below_threshold_{experience.score}",
                action="prune",
            )
            self._decisions.append(d)
            return d

        # Keep high-value experiences
        if experience.score >= 0.7:
            d = GovernanceDecision(
                experience_id=experience.experience_id,
                retain=True,
                reason="high_value_experience",
                action="keep",
                metadata={"priority": "high" if experience.score >= 0.85 else "medium"},
            )
            self._decisions.append(d)
            return d

        # Default: keep
        d = GovernanceDecision(
            experience_id=experience.experience_id,
            retain=True,
            reason="standard_retention",
            action="keep",
            metadata={"priority": "low"},
        )
        self._decisions.append(d)
        return d

    def batch_evaluate(self, experiences: list[MissionExperience]) -> list[GovernanceDecision]:
        return [self.evaluate(e) for e in experiences]

    def stats(self) -> dict[str, Any]:
        decisions = self._decisions
        total = len(decisions)
        if total == 0:
            return {"total": 0, "kept": 0, "pruned": 0, "keep_rate": 0.0}
        kept = sum(1 for d in decisions if d.retain)
        return {
            "total": total,
            "kept": kept,
            "pruned": total - kept,
            "keep_rate": round(kept / total, 4),
            "by_action": {
                action: sum(1 for d in decisions if d.action == action)
                for action in ("keep", "archive", "prune")
            },
        }

    def decisions(self) -> list[GovernanceDecision]:
        return list(self._decisions)

    def clear(self) -> None:
        self._decisions.clear()
