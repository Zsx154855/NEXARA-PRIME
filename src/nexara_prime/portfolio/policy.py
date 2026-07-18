"""Portfolio decision policy — structured priority scoring, never natural-language-only."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nexara_prime.portfolio.models import (
    ProgramRecord,
    ProgramStatus,
    OwnerDirective,
)


@dataclass
class PriorityScore:
    value: float = 0.0
    value_component: float = 0.0
    urgency_component: float = 0.0
    dependency_unblock_component: float = 0.0
    strategic_alignment_component: float = 0.0
    owner_priority_component: float = 0.0
    risk_penalty: float = 0.0
    effort_penalty: float = 0.0
    external_wait_penalty: float = 0.0
    resource_conflict_penalty: float = 0.0
    breakdown: dict[str, float] = None  # type: ignore

    def __post_init__(self):
        if self.breakdown is None:
            self.breakdown = {
                "value": round(self.value_component, 2),
                "urgency": round(self.urgency_component, 2),
                "dependency_unblock": round(self.dependency_unblock_component, 2),
                "strategic_alignment": round(self.strategic_alignment_component, 2),
                "owner_priority": round(self.owner_priority_component, 2),
                "risk_penalty": round(-self.risk_penalty, 2),
                "effort_penalty": round(-self.effort_penalty, 2),
                "external_wait_penalty": round(-self.external_wait_penalty, 2),
                "resource_conflict_penalty": round(-self.resource_conflict_penalty, 2),
            }


class PortfolioPolicy:
    """Structured portfolio decision policies.

    Default formula:
      priority_score = value + urgency + dependency_unblock_value
                       + strategic_alignment + owner_priority
                       - risk - estimated_effort
                       - external_wait_penalty - resource_conflict
    """

    VALUE_WEIGHT: float = 1.0
    URGENCY_WEIGHT: float = 1.0
    DEPENDENCY_UNBLOCK_WEIGHT: float = 0.8
    STRATEGIC_ALIGNMENT_WEIGHT: float = 0.5
    OWNER_PRIORITY_WEIGHT: float = 1.5
    RISK_WEIGHT: float = 1.0
    EFFORT_WEIGHT: float = 0.7
    EXTERNAL_WAIT_PENALTY: float = 3.0
    RESOURCE_CONFLICT_PENALTY: float = 2.0

    def score_program(self, program: ProgramRecord) -> PriorityScore:
        """Compute structured priority score for a program."""
        value_c = program.value_score * self.VALUE_WEIGHT
        urgency_c = program.urgency_score * self.URGENCY_WEIGHT

        dep_unblock = sum(
            1.0 for d in program.dependencies if d.dependency_type == "hard"
        ) * self.DEPENDENCY_UNBLOCK_WEIGHT

        strategic = program.priority * 0.5 * self.STRATEGIC_ALIGNMENT_WEIGHT
        owner_priority = 0.0  # May be boosted by directives

        risk_p = program.risk_score * self.RISK_WEIGHT
        effort_p = program.effort_score * self.EFFORT_WEIGHT

        external_wait_p = (
            self.EXTERNAL_WAIT_PENALTY
            if program.status == ProgramStatus.WAIT_EXTERNAL
            else 0.0
        )

        resource_conflict_p = 0.0  # Computed externally

        total = (
            value_c + urgency_c + dep_unblock + strategic + owner_priority
            - risk_p - effort_p - external_wait_p - resource_conflict_p
        )

        return PriorityScore(
            value=round(total, 2),
            value_component=value_c,
            urgency_component=urgency_c,
            dependency_unblock_component=dep_unblock,
            strategic_alignment_component=strategic,
            owner_priority_component=owner_priority,
            risk_penalty=risk_p,
            effort_penalty=effort_p,
            external_wait_penalty=external_wait_p,
            resource_conflict_penalty=resource_conflict_p,
        )

    def apply_owner_directive(
        self, program: ProgramRecord, directive: OwnerDirective
    ) -> PriorityScore:
        """Boost program priority based on an active Owner directive."""
        score = self.score_program(program)
        if directive.scope == "*" or directive.scope == program.program_id:
            if directive.priority == "urgent":
                score.owner_priority_component += 5.0
            elif directive.priority == "high":
                score.owner_priority_component += 3.0
            elif directive.priority == "normal":
                score.owner_priority_component += 1.0
            score.value = round(
                score.value + score.owner_priority_component, 2
            )
            score.breakdown["owner_priority"] = round(
                score.owner_priority_component, 2
            )
        return score

    def external_wait_penalized(self, program: ProgramRecord) -> bool:
        """WAIT_EXTERNAL programs are penalized to prioritize READY ones."""
        return program.status == ProgramStatus.WAIT_EXTERNAL

    def should_auto_switch(self, current: ProgramRecord, candidate: ProgramRecord) -> bool:
        """Determine if PortfolioDirector should switch from current to candidate."""
        # Never switch away from an actively running program with an open transaction
        if current.status == ProgramStatus.RUNNING and current.active_missions:
            return False
        # WAIT_EXTERNAL programs are always eligible to be switched away from
        if current.status == ProgramStatus.WAIT_EXTERNAL:
            return candidate.status == ProgramStatus.READY
        # High-risk programs that haven't been approved shouldn't auto-run
        if candidate.risk_score >= 8.0:
            return False
        current_score = self.score_program(current)
        candidate_score = self.score_program(candidate)
        return candidate_score.value > current_score.value + 1.0  # hysteresis

    def evaluate_review_budget(self, program: ProgramRecord) -> dict[str, Any]:
        """Evaluate review budget and recommend action."""
        rb = program.review_budget
        if rb.budget_exhausted and not self._has_blocking_issues(program):
            return {
                "action": "merge_readiness",
                "reason": f"Review budget exhausted ({rb.cycles_used}/{rb.max_cycles} cycles), no P0/P1 blocking",
                "program_id": program.program_id,
            }
        if rb.repeated_root_cause_detected:
            return {
                "action": "structural_fix_required",
                "reason": f"Root cause repeated {rb.repeated_root_cause_limit}+ times — structural fix required",
                "program_id": program.program_id,
                "root_causes": dict(rb.root_cause_counts),
            }
        return {"action": "continue", "program_id": program.program_id}

    @staticmethod
    def _has_blocking_issues(program: ProgramRecord) -> bool:
        """Check if program has P0 or P1 issues."""
        return any(
            r.severity in ("critical", "high") and r.is_active
            for r in (program.metadata.get("risks") or [])
        )
