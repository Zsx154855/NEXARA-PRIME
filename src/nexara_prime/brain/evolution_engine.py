"""EvolutionEngine — unified evolution loop with human approval boundary.

Collects candidates from reflection/experience/preference/intelligence,
evaluates proposals, gates through AutonomousBoundary, applies approved changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from ..models import now_iso

if TYPE_CHECKING:
    from .memory_controller import MemoryController

# ── Proposal lifecycle ──
PROPOSAL_STATUSES = ["DRAFT", "EVALUATING", "APPROVAL_REQUIRED", "APPROVED", "APPLIED", "VERIFIED", "ARCHIVED"]
VALID_TRANSITIONS = {
    "DRAFT": ["EVALUATING"],
    "EVALUATING": ["APPROVAL_REQUIRED", "DRAFT"],
    "APPROVAL_REQUIRED": ["APPROVED", "DRAFT"],
    "APPROVED": ["APPLIED"],
    "APPLIED": ["VERIFIED"],
    "VERIFIED": ["ARCHIVED"],
    "ARCHIVED": [],
}
SOURCE_TYPES = ["Reflection", "Experience", "Preference", "Mission_Intelligence"]
TARGET_AREAS = ["Memory", "Preference", "Experience", "Reasoning", "Mission_Strategy"]


@dataclass
class EvolutionProposal:
    proposal_id: str
    source_type: str
    target_area: str
    current_state: str
    proposed_change: str
    expected_benefit: str
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.5
    risk_score: float = 0.5
    approval_required: bool = True
    status: str = "DRAFT"
    metadata: dict[str, Any] = field(default_factory=dict)


class EvolutionController:
    """Unified evolution loop: collect → evaluate → approve → apply → verify → archive."""

    def __init__(self, memory_controller: MemoryController) -> None:
        self._mc = memory_controller

    # ── Collect ──

    def collect_candidates(self) -> list[EvolutionProposal]:
        proposals: list[EvolutionProposal] = []
        proposals.extend(self._from_reflections())
        proposals.extend(self._from_experiences())
        proposals.extend(self._from_preferences())
        proposals.extend(self._from_intelligence())
        return proposals

    def _from_reflections(self) -> list[EvolutionProposal]:
        records = self._mc.recall("global", layer="episodic")
        return [
            self._make_proposal("Reflection", "Memory", r.get("content", ""),
                                evidence_refs=[r.get("evidence_id", "")])
            for r in records if r.get("key", "").startswith("reflection:") and r.get("status") == "active"
        ]

    def _from_experiences(self) -> list[EvolutionProposal]:
        records = self._mc.rank_retrieve("failure pattern", top_k=10, layers=["episodic"], min_confidence=0.2)
        results = []
        for r in records:
            if r.get("kind") == "experience":
                data = json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
                if not data.get("success", True):
                    results.append(self._make_proposal(
                        "Experience", "Experience",
                        f"Improve pattern: {data.get('action', 'unknown')}",
                        evidence_refs=[r.get("evidence_id", "")],
                        confidence=max(0.3, 1.0 - float(r.get("confidence", 0.5))),
                    ))
        return results

    def _from_preferences(self) -> list[EvolutionProposal]:
        records = self._mc.rank_retrieve("preference", top_k=10, layers=["semantic"], min_confidence=0.5)
        return [
            self._make_proposal("Preference", "Preference",
                                f"Optimize: {r.get('key', '')}", evidence_refs=[r.get("evidence_id", "")],
                                confidence=float(r.get("confidence", 0.5)))
            for r in records
        ]

    def _from_intelligence(self) -> list[EvolutionProposal]:
        records = self._mc.recall("global", layer="procedural")
        return [
            self._make_proposal("Mission_Intelligence", "Mission_Strategy",
                                f"Strategy: {r.get('key', '')}", evidence_refs=[r.get("evidence_id", "")],
                                confidence=float(r.get("confidence", 0.5)))
            for r in records if r.get("key", "").startswith("insight:") and r.get("status") == "active"
        ]

    def _make_proposal(self, source: str, target: str, change: str, evidence_refs=None, confidence: float = 0.5) -> EvolutionProposal:
        import hashlib
        pid = hashlib.sha256(f"{source}{target}{change}{now_iso()}".encode()).hexdigest()[:12]
        return EvolutionProposal(
            proposal_id=f"evo_{pid}", source_type=source, target_area=target,
            current_state="baseline", proposed_change=change,
            expected_benefit=f"Improve {target} via {source}", evidence_refs=evidence_refs or [],
            confidence=confidence, risk_score=1.0 - confidence,
        )

    # ── Evaluate ──

    def evaluate_proposal(self, proposal: EvolutionProposal) -> EvolutionProposal:
        proposal.status = "EVALUATING"
        proposal.risk_score = max(0.1, min(0.9, proposal.risk_score))
        proposal.confidence = max(0.1, min(0.9, proposal.confidence))
        if proposal.risk_score > 0.7 or proposal.confidence < 0.3:
            proposal.status = "DRAFT"
            return proposal
        if proposal.risk_score > 0.4:
            proposal.approval_required = True
            proposal.status = "APPROVAL_REQUIRED"
        else:
            proposal.approval_required = False
            proposal.status = "APPROVED"
        return proposal

    def require_approval(self, proposal: EvolutionProposal) -> bool:
        return proposal.approval_required or proposal.risk_score > 0.4

    # ── Apply ──

    def apply_evolution(self, proposal: EvolutionProposal) -> EvolutionProposal:
        if proposal.status != "APPROVED":
            return proposal
        proposal.status = "APPLIED"
        self._record_proposal(proposal)
        return proposal

    def reject_proposal(self, proposal: EvolutionProposal) -> EvolutionProposal:
        proposal.status = "DRAFT"
        proposal.risk_score = min(1.0, proposal.risk_score + 0.1)
        return proposal

    # ── Verify ──

    def verify_evolution(self, proposal: EvolutionProposal) -> EvolutionProposal:
        if proposal.status != "APPLIED":
            return proposal
        proposal.status = "VERIFIED"
        proposal.confidence = min(1.0, proposal.confidence + 0.1)
        self._record_proposal(proposal)
        return proposal

    # ── Archive ──

    def archive_evolution(self, proposal: EvolutionProposal) -> EvolutionProposal:
        proposal.status = "ARCHIVED"
        self._record_proposal(proposal)
        return proposal

    # ── History ──

    def get_evolution_history(self, limit: int = 50) -> list[EvolutionProposal]:
        records = self._mc.recall("global", layer="procedural")
        results = []
        for r in records:
            if r.get("key", "").startswith("evolution:") and r.get("status") == "active":
                try:
                    data = json.loads(r.get("content", "{}")) if isinstance(r.get("content"), str) else r.get("content", {})
                    results.append(EvolutionProposal(
                        proposal_id=data.get("proposal_id", ""),
                        source_type=data.get("source_type", ""),
                        target_area=data.get("target_area", ""),
                        current_state=data.get("current_state", ""),
                        proposed_change=data.get("proposed_change", ""),
                        expected_benefit=data.get("expected_benefit", ""),
                        evidence_refs=data.get("evidence_refs", []),
                        confidence=float(data.get("confidence", 0.5)),
                        risk_score=float(data.get("risk_score", 0.5)),
                        approval_required=data.get("approval_required", True),
                        status=data.get("status", "DRAFT"),
                    ))
                except (json.JSONDecodeError, KeyError):
                    pass
        return results[:limit]

    def _record_proposal(self, proposal: EvolutionProposal) -> str:
        content = json.dumps({
            "proposal_id": proposal.proposal_id,
            "source_type": proposal.source_type,
            "target_area": proposal.target_area,
            "current_state": proposal.current_state,
            "proposed_change": proposal.proposed_change,
            "expected_benefit": proposal.expected_benefit,
            "evidence_refs": proposal.evidence_refs,
            "confidence": proposal.confidence,
            "risk_score": proposal.risk_score,
            "approval_required": proposal.approval_required,
            "status": proposal.status,
        })
        return self._mc.commit(
            mission_id="global", key=f"evolution:{proposal.proposal_id}",
            content=content, kind="procedural",
            confidence=proposal.confidence,
        )

    def summarize(self) -> dict[str, Any]:
        history = self.get_evolution_history(limit=100)
        statuses = {"DRAFT": 0, "APPROVED": 0, "APPLIED": 0, "VERIFIED": 0, "ARCHIVED": 0}
        for p in history:
            statuses[p.status] = statuses.get(p.status, 0) + 1
        return {
            "total_proposals": len(history),
            "by_status": statuses,
            "by_source": {s: sum(1 for p in history if p.source_type == s) for s in SOURCE_TYPES},
            "by_target": {t: sum(1 for p in history if p.target_area == t) for t in TARGET_AREAS},
        }
