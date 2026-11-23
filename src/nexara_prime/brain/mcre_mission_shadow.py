"""Optional read-only MCRE observer for existing NEXARA Mission objects.

M1 boundary: this module DOES NOT patch NexaraRuntime, dispatch workers, write
mission state, spend budget, produce verified evidence, or authorize tools.
The caller must supply repository/environment/scope truth from trusted host
state, not from user-authored mission text or previous LLM output.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .mcre_evidence_binding import EvidenceReader, EvidenceStoreBinding
from .mcre_shadow import ContextRef, DecisionAdvice, DecisionRequest, MCREShadow


@dataclass(frozen=True)
class ShadowSnapshot:
    project_id: str
    repo_sha: str | None
    environment_id: str | None
    scope_id: str
    context_refs: tuple[ContextRef, ...] = ()
    remaining_tokens: int | None = None
    retries_without_new_evidence: int = 0
    observed_cost_usd: float | None = None


class MissionShadowObserver:
    """Builds a deterministic advice event from a Mission and host snapshot.

    Source-backed evidence resolution only; unsupported or missing trusted
    evidence readers conservatively produce RESEARCH, never REUSE.
    """

    name = "mcre_mission_shadow"

    def __init__(self, evidence_store: EvidenceReader | None = None) -> None:
        self._binding = EvidenceStoreBinding(evidence_store) if evidence_store is not None else None
        self._advisor = MCREShadow(self._binding.verify_context if self._binding is not None else None)

    @staticmethod
    def _risk(value: Any) -> str:
        risk = getattr(value, "value", value)
        return risk if isinstance(risk, str) else "UNKNOWN"

    @staticmethod
    def _budget(mission: Any) -> int | None:
        """Read only the existing ResourceBudget/BudgetUsage *snapshot*.

        Absence of reported usage does not mean 0 usage; therefore unknown
        budget information remains unknown, not 100% available.
        """
        budget = getattr(mission, "resource_budget", None)
        usage = getattr(mission, "budget_usage", None)
        if not isinstance(budget, dict) or not isinstance(usage, dict):
            return None
        if budget.get("mission_id") not in (None, getattr(mission, "mission_id", None)):
            return None
        if usage.get("mission_id") not in (None, getattr(mission, "mission_id", None)):
            return None
        if (budget.get("budget_id") is not None or usage.get("budget_id") is not None):
            if not budget.get("budget_id") or budget.get("budget_id") != usage.get("budget_id"):
                return None
        total = budget.get("token_budget")
        used = usage.get("tokens_used")
        if type(total) is not int or type(used) is not int or total < 0 or used < 0:
            return None
        return max(0, total - used)

    def observe(self, mission: Any, snapshot: ShadowSnapshot) -> DecisionAdvice:
        spec = getattr(mission, "spec", None)
        mission_id = getattr(mission, "mission_id", None)
        if not isinstance(mission_id, str) or not mission_id:
            raise ValueError("mission_id_missing")
        if spec is None or getattr(spec, "mission_id", None) != mission_id:
            raise ValueError("mission_spec_identity_mismatch")
        objective = getattr(spec, "objective", None)
        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("mission_objective_missing")
        # No implicit project ownership or permission from the Mission's text.
        if not snapshot.project_id or not snapshot.scope_id:
            raise ValueError("trusted_project_scope_missing")
        reported_remaining = self._budget(mission)
        supplied_remaining = snapshot.remaining_tokens
        # Conservative choice when host snapshot and the durable Mission disagree.
        # A positive host number must not override an exhausted Mission budget.
        tokens = min(reported_remaining, supplied_remaining) if (reported_remaining is not None
                 and supplied_remaining is not None) else (reported_remaining if supplied_remaining is None
                 else supplied_remaining)
        request = DecisionRequest(
            mission_id=mission_id,
            project_id=snapshot.project_id,
            objective=objective,
            repo_sha=snapshot.repo_sha,
            environment_id=snapshot.environment_id,
            scope_id=snapshot.scope_id,
            risk_level=self._risk(getattr(spec, "risk_level", "UNKNOWN")),
            remaining_tokens=tokens,
            retries_without_new_evidence=snapshot.retries_without_new_evidence,
            known_cost_usd=snapshot.observed_cost_usd,
        )
        return self._advisor.advise(request, snapshot.context_refs)
