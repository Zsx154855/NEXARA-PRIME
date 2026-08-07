"""EvolutionEngine — learns from mission outcomes.

Records: what worked, what failed, what models were used, routing decisions.
Feeds back into model policy refinement.

EvolutionController — manages the evolution proposal lifecycle:
collect candidates from memory, evaluate risk, manage approval boundaries,
and drive proposals through apply→verify→archive.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..models import new_id, now_iso


@dataclass
class EvolutionProposal:
    """A single evolution candidate with lifecycle state."""

    source_type: str
    target_area: str
    description: str
    status: str = "DRAFT"
    risk_score: float = 0.0
    approval_required: bool = False
    confidence: float = 1.0


class EvolutionEngine:
    """Tracks mission outcomes for continuous improvement.

    Does NOT modify policies directly. Produces observations that the
    ChiefBrainKernel uses to refine model_policy and routing.
    """

    name = "evolution_engine"

    def __init__(self) -> None:
        self._observations: list[dict[str, Any]] = []

    def observe(
        self,
        mission_id: str,
        provider: str,
        model: str,
        success: bool,
        tokens: int,
        cost: float,
        routing_decision: dict[str, Any] | None = None,
    ) -> str:
        """Record a mission outcome observation."""
        obs_id = new_id("evo")
        observation = {
            "observation_id": obs_id,
            "mission_id": mission_id,
            "provider": provider,
            "model": model,
            "success": success,
            "tokens": tokens,
            "cost": cost,
            "routing_decision": routing_decision,
            "timestamp": now_iso(),
        }
        self._observations.append(observation)
        return obs_id

    def insights(self) -> dict[str, Any]:
        """Generate insights from observations."""
        if not self._observations:
            return {"status": "no_data"}

        total = len(self._observations)
        successes = sum(1 for o in self._observations if o["success"])
        total_cost = sum(o["cost"] for o in self._observations)
        total_tokens = sum(o["tokens"] for o in self._observations)
        providers_used = list({o["provider"] for o in self._observations})
        models_used = list({o["model"] for o in self._observations})

        return {
            "total_missions": total,
            "success_rate": round(successes / total, 2) if total else 0,
            "total_cost": round(total_cost, 8),
            "total_tokens": total_tokens,
            "avg_tokens_per_mission": total_tokens // total if total else 0,
            "providers_used": providers_used,
            "models_used": models_used,
        }

    def health(self) -> dict[str, Any]:
        return {"observations": len(self._observations), "insights": self.insights()}


class EvolutionController:
    """Controls the evolution proposal lifecycle.

    Collects candidates from memory reflections, failures, preferences,
    and mission intelligence; evaluates risk/confidence thresholds;
    manages approval boundaries; and drives proposals through
    apply → verify → archive.
    """

    def __init__(self, mc: Any) -> None:
        self._mc = mc
        self._history: list[EvolutionProposal] = []

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    def _make_proposal(
        self,
        source_type: str,
        target_area: str,
        description: str,
        confidence: float = 1.0,
    ) -> EvolutionProposal:
        return EvolutionProposal(
            source_type=source_type,
            target_area=target_area,
            description=description,
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # Candidate collection
    # ------------------------------------------------------------------

    def collect_candidates(self) -> list[EvolutionProposal]:
        """Scan memory layers for evolution candidates."""
        candidates: list[EvolutionProposal] = []

        episodic = self._mc.recall("global", layer="episodic")

        # Reflections
        for rec in episodic:
            key = str(rec.get("key", ""))
            if "reflection:" not in key:
                continue
            content = self._parse_json(rec.get("content", "{}"))
            lessons = content.get("lessons", ["reflection"])
            desc = str(lessons[0]) if lessons else "reflection"
            candidates.append(
                self._make_proposal(
                    "Reflection",
                    "Memory",
                    desc,
                    confidence=float(rec.get("confidence", 0.5)),
                )
            )

        # Experience / failures
        for rec in episodic:
            key = str(rec.get("key", ""))
            if "exp:" not in key:
                continue
            content = self._parse_json(rec.get("content", "{}"))
            action = str(content.get("action", "failure"))
            candidates.append(
                self._make_proposal(
                    "Experience",
                    "Memory",
                    action,
                    confidence=float(rec.get("confidence", 0.5)),
                )
            )

        # Preferences (semantic layer)
        semantic = self._mc.recall("global", layer="semantic")
        for rec in semantic:
            if rec.get("kind") == "preference":
                candidates.append(
                    self._make_proposal(
                        "Preference",
                        "Knowledge",
                        "preference",
                        confidence=float(rec.get("confidence", 0.5)),
                    )
                )

        # Intelligence (procedural layer)
        procedural = self._mc.recall("global", layer="procedural")
        for rec in procedural:
            key = str(rec.get("key", ""))
            if "insight:" in key:
                candidates.append(
                    self._make_proposal(
                        "Mission_Intelligence",
                        "Strategy",
                        "intelligence",
                        confidence=float(rec.get("confidence", 0.5)),
                    )
                )

        return candidates

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_proposal(self, proposal: EvolutionProposal) -> EvolutionProposal:
        """Score a proposal and assign its status.

        Thresholds:
        - confidence < 0.2  or  risk > 0.7  → DRAFT
        - confidence >= 0.4  and  risk <= 0.3  → APPROVED
        - otherwise → APPROVAL_REQUIRED
        """
        conf = proposal.confidence
        risk = proposal.risk_score

        if conf < 0.2 or risk > 0.7:
            proposal.status = "DRAFT"
            proposal.approval_required = False
        elif conf >= 0.4 and risk <= 0.3:
            proposal.status = "APPROVED"
            proposal.approval_required = False
        else:
            proposal.status = "APPROVAL_REQUIRED"
            proposal.approval_required = True

        return proposal

    def require_approval(self, proposal: EvolutionProposal) -> bool:
        """Returns True when the proposal crosses the approval boundary."""
        return proposal.risk_score > 0.4 and proposal.confidence < 0.4

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def apply_evolution(self, proposal: EvolutionProposal) -> EvolutionProposal:
        """Apply an approved proposal.  Non-approved proposals stay DRAFT."""
        if proposal.status == "APPROVED":
            proposal.status = "APPLIED"
            self._record_proposal(proposal)
        else:
            proposal.status = "DRAFT"
        return proposal

    def reject_proposal(self, proposal: EvolutionProposal) -> EvolutionProposal:
        """Reject a proposal that was awaiting approval."""
        if proposal.status == "APPROVAL_REQUIRED":
            proposal.status = "DRAFT"
            proposal.risk_score = max(proposal.risk_score, 0.51)
        return proposal

    def verify_evolution(self, proposal: EvolutionProposal) -> EvolutionProposal:
        """Verify an applied proposal.  Only transitions from APPLIED."""
        if proposal.status == "APPLIED":
            proposal.status = "VERIFIED"
            self._record_proposal(proposal)
        return proposal

    def archive_evolution(self, proposal: EvolutionProposal) -> EvolutionProposal:
        """Archive a proposal (accepts any status)."""
        proposal.status = "ARCHIVED"
        self._record_proposal(proposal)
        return proposal

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def _record_proposal(self, proposal: EvolutionProposal) -> None:
        """Persist a proposal into history and memory."""
        self._history.append(proposal)
        self._mc.commit(
            mission_id="global",
            key=f"evolution:{proposal.source_type}:{proposal.target_area}",
            content=json.dumps(
                {
                    "source_type": proposal.source_type,
                    "target_area": proposal.target_area,
                    "description": proposal.description,
                    "status": proposal.status,
                }
            ),
            kind="procedural",
            confidence=proposal.confidence,
        )

    def get_evolution_history(self) -> list[EvolutionProposal]:
        """Return all recorded proposals."""
        return list(self._history)

    def summarize(self) -> dict[str, Any]:
        """Return a summary of evolution activity."""
        return {"total_proposals": len(self._history)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(str(raw))
        except (json.JSONDecodeError, TypeError):
            return {}
