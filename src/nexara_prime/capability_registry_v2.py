from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import CapabilityScore, RiskLevel, new_id, now_iso


class CapabilityRegistryV2:
    """Evidence-scored capability registry with decay and confidence gating.

    Scores are derived from real mission outcomes, not static self-reports.
    Confidence increases only when evidence_count >= 3.
    Scores decay over time if not updated (0.1/day after 7 days, min 0.1).
    """

    def __init__(self) -> None:
        self._scores: dict[str, CapabilityScore] = {}
        self._mission_history: dict[str, list[dict[str, Any]]] = (
            {}
        )  # capability_id -> list of mission outcomes

    # ── Registration ────────────────────────────────────────────────

    def register(
        self,
        capability_id: str,
        name: str,
        supported_task_types: list[str] | None = None,
        tool_permissions: list[str] | None = None,
        risk_ceiling: str = RiskLevel.R1.value,
        model_requirements: list[str] | None = None,
    ) -> CapabilityScore:
        """Register a new capability with initial neutral scores."""
        score = CapabilityScore(
            capability_id=capability_id,
            name=name,
            supported_task_types=supported_task_types or [],
            tool_permissions=tool_permissions or [],
            risk_ceiling=risk_ceiling,
            model_requirements=model_requirements or [],
            historical_success_rate=0.0,
            average_latency_ms=0.0,
            average_token_cost=0.0,
            recent_failure_rate=0.0,
            confidence=0.5,
            evidence_count=0,
            last_updated=now_iso(),
            source_evidence=[],
            schema_version=2,
        )
        self._scores[capability_id] = score
        self._mission_history[capability_id] = []
        return score

    # ── Score Update ────────────────────────────────────────────────

    def update_score(
        self,
        capability_id: str,
        mission_success: bool,
        latency_ms: float,
        token_cost: float,
        evidence_ids: list[str] | None = None,
    ) -> CapabilityScore | None:
        """Update a capability's score with real mission outcome data.

        - historical_success_rate: ratio of successes to total missions
        - recent_failure_rate: from the last 10 missions
        - confidence: increases to evidence_count/10 ONLY when evidence_count >= 3
        - average_latency_ms / average_token_cost: running averages
        - evidence_count: incremented by number of new evidence IDs
        """
        score = self._scores.get(capability_id)
        if score is None:
            return None

        evidence_ids = evidence_ids or []

        # Record outcome
        outcome: dict[str, Any] = {
            "success": mission_success,
            "latency_ms": latency_ms,
            "token_cost": token_cost,
            "evidence_ids": evidence_ids,
            "timestamp": now_iso(),
        }
        self._mission_history.setdefault(capability_id, []).append(outcome)

        # Compute historical success rate
        history = self._mission_history[capability_id]
        total_missions = len(history)
        successes = sum(1 for o in history if o["success"])
        failures = total_missions - successes
        score.historical_success_rate = (
            successes / total_missions if total_missions > 0 else 0.0
        )

        # Recent failure rate from last 10 missions
        recent = history[-10:]
        recent_failures = sum(1 for o in recent if not o["success"])
        score.recent_failure_rate = recent_failures / len(recent) if recent else 0.0

        # Running average latency
        all_latencies = [o["latency_ms"] for o in history]
        score.average_latency_ms = (
            sum(all_latencies) / len(all_latencies) if all_latencies else 0.0
        )

        # Running average token cost
        all_costs = [o["token_cost"] for o in history]
        score.average_token_cost = (
            sum(all_costs) / len(all_costs) if all_costs else 0.0
        )

        # Evidence count
        new_evidence = [eid for eid in evidence_ids if eid not in score.source_evidence]
        score.evidence_count += len(new_evidence)
        score.source_evidence.extend(new_evidence)

        # Confidence: increases ONLY with evidence_count >= 3
        if score.evidence_count >= 3:
            score.confidence = min(score.evidence_count / 10.0, 1.0)
        else:
            # Low confidence for insufficient evidence
            score.confidence = max(0.3, score.evidence_count * 0.1)

        score.last_updated = now_iso()
        return score

    # ── Decay ────────────────────────────────────────────────────────

    def _apply_decay(self, score: CapabilityScore) -> None:
        """Reduce confidence if last_updated > 7 days.

        Decay: 0.1/day after 7 days. Never drops below 0.1.
        """
        try:
            last = datetime.fromisoformat(score.last_updated)
        except (ValueError, TypeError):
            return

        now = datetime.now(timezone.utc)
        days_since_update = (now - last).total_seconds() / 86400.0

        if days_since_update > 7.0:
            days_overdue = days_since_update - 7.0
            decay = days_overdue * 0.1
            score.confidence = max(0.1, score.confidence - decay)

    # ── Query ───────────────────────────────────────────────────────

    def get_score(self, capability_id: str) -> CapabilityScore | None:
        """Get the current score for a capability, applying decay first."""
        score = self._scores.get(capability_id)
        if score is None:
            return None
        self._apply_decay(score)
        return score

    def list_capable(
        self,
        task_type: str,
        min_confidence: float = 0.5,
    ) -> list[CapabilityScore]:
        """List capability scores supporting a given task type with minimum confidence.

        Applies decay before filtering.
        """
        results: list[CapabilityScore] = []
        for score in self._scores.values():
            self._apply_decay(score)
            if task_type.lower() in (
                tt.lower() for tt in score.supported_task_types
            ):
                if score.confidence >= min_confidence:
                    results.append(score)
        # Sort by confidence descending, then by success rate descending
        results.sort(
            key=lambda s: (s.confidence, s.historical_success_rate),
            reverse=True,
        )
        return results

    def list_all(self) -> list[CapabilityScore]:
        """List all registered capability scores with decay applied."""
        for score in self._scores.values():
            self._apply_decay(score)
        return list(self._scores.values())

    def get_mission_history(
        self,
        capability_id: str,
    ) -> list[dict[str, Any]]:
        """Get raw mission outcome history for a capability."""
        return self._mission_history.get(capability_id, [])
