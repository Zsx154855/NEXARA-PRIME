"""Read-only MCRE advisor: no model calls, dispatch, memory writes or authority.

Integrates *beside* the existing Cognitive Core, ResourceBudget, TokenGovernor,
Scheduler and Trusted Gate.  The owning runtime alone may act on a suggestion.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ContextRef:
    evidence_id: str
    project_id: str
    repo_sha: str
    environment_id: str
    scope_id: str
    content_digest: str


@dataclass(frozen=True)
class DecisionRequest:
    mission_id: str
    project_id: str
    objective: str
    repo_sha: str | None
    environment_id: str | None
    scope_id: str
    risk_level: str = "R1"
    remaining_tokens: int | None = None
    retries_without_new_evidence: int = 0
    known_cost_usd: float | None = None


@dataclass(frozen=True)
class DecisionAdvice:
    mission_id: str
    task_key: str
    strategy: str  # RESEARCH | REUSE | ESCALATE | DEFER
    reason_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    known_cost_usd: float | None
    shadow_only: bool = True
    execution_authorized: bool = False

    def otel_attributes(self) -> dict[str, str | int | float]:
        """Privacy-minimal attributes; no prompts, files, keys or invented costs."""
        attrs: dict[str, str | int | float] = {
            "nexara.mcre.strategy": self.strategy,
            "nexara.mcre.shadow_only": str(self.shadow_only).lower(),
            "nexara.mcre.evidence_count": len(self.evidence_ids),
        }
        if self.known_cost_usd is not None:
            attrs["nexara.mcre.observed_cost_usd"] = self.known_cost_usd
        return attrs


class MCREShadow:
    """Deterministic advisory adapter; does not replace any production gate.

    `verify_evidence` must validate the ENTIRE reference (evidence ID, project,
    repo head, environment, scope, digest) against trusted EvidenceStore bytes.
    Merely checking that an evidence ID exists is insufficient.
    Missing resolver means fail-closed for *reusing* evidence.
    Its result never grants permission to execute any operation.
    """
    name = "mcre_shadow"

    def __init__(self, verify_evidence: Callable[[ContextRef], bool] | None = None) -> None:
        self._verify_evidence = verify_evidence

    @staticmethod
    def task_key(req: DecisionRequest) -> str:
        fields = [req.project_id, req.objective.strip().casefold(),
                  req.repo_sha, req.environment_id, req.scope_id]
        payload = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def advise(self, req: DecisionRequest, refs: tuple[ContextRef, ...] = ()) -> DecisionAdvice:
        if not all([req.mission_id, req.project_id, req.objective.strip(), req.scope_id]):
            raise ValueError("mission, project, objective and scope are required")
        if req.remaining_tokens is not None and req.remaining_tokens < 0:
            raise ValueError("remaining_tokens cannot be negative")
        if req.retries_without_new_evidence < 0:
            raise ValueError("retry count cannot be negative")
        if req.known_cost_usd is not None and req.known_cost_usd < 0:
            raise ValueError("known cost cannot be negative")

        reasons: list[str] = []
        if req.known_cost_usd is None:
            reasons.append("COST_UNKNOWN")
        if req.remaining_tokens == 0:
            strategy = "DEFER"
            reasons.append("TOKEN_BUDGET_EXHAUSTED")
            selected: tuple[str, ...] = ()
        elif req.retries_without_new_evidence >= 2:
            strategy = "DEFER"
            reasons.append("REPEATED_FAILURE_NO_NEW_EVIDENCE")
            selected = ()
        elif req.risk_level not in ("R0", "R1"):
            strategy = "ESCALATE"
            reasons.append("RISK_REQUIRES_EXISTING_TRUSTED_GATE")
            selected = ()
        elif not req.repo_sha or not req.environment_id:
            strategy = "RESEARCH"
            reasons.append("SOURCE_VERSION_UNKNOWN")
            selected = ()
        else:
            verified: list[str] = []
            for ref in refs:
                if (ref.project_id != req.project_id or ref.repo_sha != req.repo_sha
                        or ref.environment_id != req.environment_id or ref.scope_id != req.scope_id
                        or not ref.evidence_id or not ref.content_digest):
                    continue
                if self._verify_evidence is None:
                    continue
                try:
                    if self._verify_evidence(ref) is True:
                        verified.append(ref.evidence_id)
                except Exception:
                    # Evidence lookup failure must not enable a cached result.
                    continue
            selected = tuple(sorted(set(verified)))
            strategy = "REUSE" if selected else "RESEARCH"
            reasons.append("VERSION_BOUND_EVIDENCE" if selected else "NO_TRUSTED_CONTEXT")
        return DecisionAdvice(req.mission_id, self.task_key(req), strategy,
                              tuple(reasons), selected, req.known_cost_usd)
