from __future__ import annotations

from typing import Any

from .models import (
    AdaptiveMode,
    EscalationDecision,
    Mission,
    MissionTriageResult,
    new_id,
    now_iso,
)


class EscalationEngine:
    """Progressive escalation engine for adaptive missions.

    All escalations and de-escalations are auditable — every decision
    produces an EscalationDecision record stored in the mission history.
    """

    def __init__(self) -> None:
        self._escalation_count: int = 0

    # ── Escalation Decisions ────────────────────────────────────────

    def should_escalate(
        self,
        mission: Mission,
        triage_result: MissionTriageResult,
        current_issues: list[dict[str, Any]],
    ) -> EscalationDecision | None:
        """Evaluate whether to escalate the mission's adaptive mode.

        Returns an EscalationDecision if any escalation trigger is met,
        or None if no escalation is warranted.

        Triggers:
        - uncertainty > threshold (0.7)
        - validation_failed
        - tool_failed
        - disagreement_detected
        - policy_requires
        - user_requested
        - external_side_effect_detected
        - evidence_insufficient
        """
        current_mode = AdaptiveMode(mission.adaptive_mode)

        # Can't escalate past S3 (governed)
        if current_mode == AdaptiveMode.S3:
            return None

        # Determine which triggers fire
        active_triggers: list[str] = []
        max_severity: float = 0.0

        for issue in current_issues:
            trigger = issue.get("trigger", "")
            severity = issue.get("severity", 0.5)
            max_severity = max(max_severity, severity)

            if trigger == "uncertainty_high":
                threshold = issue.get("threshold", 0.7)
                if triage_result.uncertainty > threshold:
                    active_triggers.append("uncertainty > threshold")

            elif trigger == "validation_failed":
                if issue.get("value", False):
                    active_triggers.append("validation_failed")

            elif trigger == "tool_failed":
                tool_name = issue.get("tool_name", "unknown")
                if issue.get("value", False):
                    active_triggers.append(f"tool_failed:{tool_name}")

            elif trigger == "disagreement_detected":
                count = issue.get("count", 0)
                if count > 0:
                    active_triggers.append(f"disagreement_detected(x{count})")

            elif trigger == "policy_requires":
                if issue.get("value", False):
                    active_triggers.append("policy_requires")

            elif trigger == "user_requested":
                if issue.get("value", False):
                    active_triggers.append("user_requested")

            elif trigger == "external_side_effect_detected":
                if issue.get("value", False):
                    active_triggers.append("external_side_effect_detected")

            elif trigger == "evidence_insufficient":
                if issue.get("value", False):
                    active_triggers.append("evidence_insufficient")

        if not active_triggers:
            return None

        # Determine escalation target mode
        mode_escalation: dict[AdaptiveMode, AdaptiveMode] = {
            AdaptiveMode.S0: AdaptiveMode.S1,
            AdaptiveMode.S1: AdaptiveMode.S2,
            AdaptiveMode.S2: AdaptiveMode.S3,
        }
        target_mode = mode_escalation.get(current_mode)
        if target_mode is None:
            return None

        reason = f"Escalation triggered: {'; '.join(active_triggers)}"
        decision = EscalationDecision(
            decision_id=new_id("escalate"),
            mission_id=mission.mission_id,
            from_mode=mission.adaptive_mode,
            to_mode=target_mode.value,
            reason=reason,
            trigger=active_triggers[0],
            approved=True,
            actor="system",
            metadata={
                "active_triggers": active_triggers,
                "severity": max_severity,
                "triage_uncertainty": triage_result.uncertainty,
                "escalation_number": self._escalation_count + 1,
            },
        )
        return decision

    # ── De-escalation Decisions ─────────────────────────────────────

    def should_de_escalate(
        self,
        mission: Mission,
        current_state: dict[str, Any],
    ) -> EscalationDecision | None:
        """Evaluate whether to de-escalate the mission's adaptive mode.

        De-escalation triggers:
        - task_resolved: mission reached a completed/resolved state
        - uncertainty_reduced: uncertainty dropped below 0.3
        - no_longer_parallel: complexity reduced below threshold
        - budget_pressure: running out of tokens/cost budget
        - reviewer_confirms_simple: independent reviewer deems task simple
        """
        current_mode = AdaptiveMode(mission.adaptive_mode)

        # Can't de-escalate below S0
        if current_mode == AdaptiveMode.S0:
            return None

        active_triggers: list[str] = []

        # task_resolved
        if current_state.get("task_resolved", False):
            active_triggers.append("task_resolved")

        # uncertainty_reduced
        uncertainty = current_state.get("uncertainty", 1.0)
        if uncertainty < 0.3:
            active_triggers.append("uncertainty_reduced")

        # no_longer_parallel
        complexity = current_state.get("complexity_score", 1.0)
        if complexity < 0.3:
            active_triggers.append("no_longer_parallel")

        # budget_pressure
        budget_remaining_pct = current_state.get("budget_remaining_pct", 100.0)
        if budget_remaining_pct < 15.0:
            active_triggers.append("budget_pressure")

        # reviewer_confirms_simple
        if current_state.get("reviewer_confirms_simple", False):
            active_triggers.append("reviewer_confirms_simple")

        if not active_triggers:
            return None

        # Determine de-escalation target mode
        mode_de_escalation: dict[AdaptiveMode, AdaptiveMode] = {
            AdaptiveMode.S3: AdaptiveMode.S2,
            AdaptiveMode.S2: AdaptiveMode.S1,
            AdaptiveMode.S1: AdaptiveMode.S0,
        }
        target_mode = mode_de_escalation.get(current_mode)
        if target_mode is None:
            return None

        reason = f"De-escalation triggered: {'; '.join(active_triggers)}"
        decision = EscalationDecision(
            decision_id=new_id("escalate"),
            mission_id=mission.mission_id,
            from_mode=mission.adaptive_mode,
            to_mode=target_mode.value,
            reason=reason,
            trigger=active_triggers[0],
            approved=True,
            actor="system",
            metadata={
                "active_triggers": active_triggers,
                "current_state": current_state,
                "de_escalation_number": self._escalation_count + 1,
            },
        )
        return decision

    # ── Execute Escalation ──────────────────────────────────────────

    def execute_escalation(
        self,
        mission: Mission,
        decision: EscalationDecision,
    ) -> dict[str, Any]:
        """Execute an escalation/de-escalation decision.

        Returns a dict with:
        - new_mode: the target adaptive mode string
        - added_roles: roles that were added
        - removed_roles: roles that were removed
        - budget_adjustments: any budget changes
        """
        self._escalation_count += 1
        from_mode = AdaptiveMode(decision.from_mode)
        to_mode = AdaptiveMode(decision.to_mode)

        added_roles: list[str] = []
        removed_roles: list[str] = []
        budget_adjustments: dict[str, Any] = {}

        # Escalation: add roles and increase budget
        if self._is_escalation(from_mode, to_mode):
            if to_mode in (AdaptiveMode.S2, AdaptiveMode.S3):
                added_roles.append("Reviewer")
                budget_adjustments["token_budget_multiplier"] = 1.5
                budget_adjustments["cost_budget_multiplier"] = 1.5
            if to_mode == AdaptiveMode.S3:
                added_roles.append("Auditor")
                budget_adjustments["verification_required"] = True
                budget_adjustments["approval_required"] = True

        # De-escalation: remove roles and reduce budget
        else:
            if from_mode == AdaptiveMode.S3:
                removed_roles.extend(["Auditor", "Reviewer"])
                budget_adjustments["token_budget_multiplier"] = 0.7
                budget_adjustments["cost_budget_multiplier"] = 0.7
                budget_adjustments["verification_required"] = False
            elif from_mode == AdaptiveMode.S2:
                removed_roles.append("Reviewer")
                budget_adjustments["token_budget_multiplier"] = 0.8
                budget_adjustments["cost_budget_multiplier"] = 0.8

        result: dict[str, Any] = {
            "new_mode": decision.to_mode,
            "added_roles": added_roles,
            "removed_roles": removed_roles,
            "budget_adjustments": budget_adjustments,
            "decision_id": decision.decision_id,
            "reason": decision.reason,
            "trigger": decision.trigger,
            "escalation_number": self._escalation_count,
        }
        return result

    # ── Audit ───────────────────────────────────────────────────────

    def get_escalation_count(self) -> int:
        """Return the total number of escalations/de-escalations executed."""
        return self._escalation_count

    # ── Internal ────────────────────────────────────────────────────

    @staticmethod
    def _is_escalation(
        from_mode: AdaptiveMode,
        to_mode: AdaptiveMode,
    ) -> bool:
        """Determine if this is an escalation (vs de-escalation)."""
        mode_rank: dict[AdaptiveMode, int] = {
            AdaptiveMode.S0: 0,
            AdaptiveMode.S1: 1,
            AdaptiveMode.S2: 2,
            AdaptiveMode.S3: 3,
        }
        from_rank = mode_rank.get(from_mode, 0)
        to_rank = mode_rank.get(to_mode, 0)
        return to_rank > from_rank
