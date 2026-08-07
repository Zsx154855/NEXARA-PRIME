"""NEXARA Council V2 — Conflict Resolver

Resolves conflicts between council agents when votes are tied,
decisions are contested, or agents disagree on outcomes.

Integrates with the voting system defined in council_rules.yaml.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from nexara_prime.council.runtime.mission_router import AgentSeat


class ConflictType(str, Enum):
    """Types of conflicts that can arise."""
    VOTE_TIE = "VOTE_TIE"               # Equal votes for/against
    VETO_EXERCISED = "VETO_EXERCISED"   # H-RED or H-JUDGE veto
    SCOPE_DISPUTE = "SCOPE_DISPUTE"     # Disagreement on scope
    APPROACH_DISPUTE = "APPROACH_DISPUTE"  # Different technical approaches
    EVIDENCE_DISPUTE = "EVIDENCE_DISPUTE"  # Disagreement on evidence sufficiency
    JURISDICTION = "JURISDICTION"       # Who has authority


class ResolutionType(str, Enum):
    """How a conflict was resolved."""
    CHAIRMAN_DECISION = "CHAIRMAN_DECISION"     # Chairman broke the tie
    JUDGE_RULING = "JUDGE_RULING"               # Judge adjudicated
    SUPERMAJORITY_OVERRIDE = "SUPERMAJORITY_OVERRIDE"  # 7/9 override
    ESCALATED_TO_HUMAN = "ESCALATED_TO_HUMAN"   # Sent to human
    COMPROMISE_REACHED = "COMPROMISE_REACHED"   # Agents found middle ground
    UNRESOLVED = "UNRESOLVED"                   # Still open


@dataclass
class Conflict:
    """A conflict between council agents."""
    conflict_id: str = field(default_factory=lambda: f"cnf-{uuid.uuid4().hex[:8]}")
    conflict_type: ConflictType = ConflictType.VOTE_TIE
    parties: list[AgentSeat] = field(default_factory=list)
    description: str = ""
    resolution: Optional[ResolutionType] = None
    resolved_by: Optional[AgentSeat] = None
    resolution_note: str = ""


class ConflictResolver:
    """Resolves council conflicts according to the Constitution and Rules.

    Resolution order:
    1. Chairman tie-break (standard votes)
    2. Judge adjudication (constitutional questions)
    3. Supermajority override (7/9 can override Chairman)
    4. Human escalation (when all else fails)
    """

    @classmethod
    def resolve_vote_tie(cls, votes: dict[AgentSeat, str], chairman_vote: str) -> str:
        """Resolve a tied vote. Chairman breaks the tie.

        Args:
            votes: Dict of agent_id -> APPROVE/REJECT/ABSTAIN
            chairman_vote: Chairman's vote direction

        Returns:
            'APPROVE' or 'REJECT'
        """
        approve_count = sum(1 for v in votes.values() if v == "APPROVE")
        reject_count = sum(1 for v in votes.values() if v == "REJECT")

        if approve_count > reject_count:
            return "APPROVE"
        elif reject_count > approve_count:
            return "REJECT"
        else:
            # Tie: Chairman decides
            return chairman_vote

    @classmethod
    def handle_veto(cls, veto_agent: AgentSeat, veto_reason: str,
                    chairman: AgentSeat = AgentSeat.CHAIRMAN,
                    judge: AgentSeat = AgentSeat.JUDGE) -> Conflict:
        """Handle a veto from H-RED or H-JUDGE.

        A veto triggers mandatory review by Chairman + Judge.
        If both uphold the veto, it stands.
        If both override, the veto is lifted (supermajority required).
        """
        conflict = Conflict(
            conflict_type=ConflictType.VETO_EXERCISED,
            parties=[veto_agent],
            description=f"Veto by {veto_agent.value}: {veto_reason}",
        )

        # Veto review process
        if veto_agent == AgentSeat.RED:
            # RED veto requires safety evidence
            conflict.resolution = ResolutionType.JUDGE_RULING
            conflict.resolved_by = judge
            conflict.resolution_note = (
                f"RED veto on safety grounds. Requires JUDGE review and "
                f"CHAIRMAN concurrence. If both override with evidence, "
                f"veto is lifted."
            )
        elif veto_agent == AgentSeat.JUDGE:
            # JUDGE veto requires constitutional basis
            conflict.resolution = ResolutionType.CHAIRMAN_DECISION
            conflict.resolved_by = chairman
            conflict.resolution_note = (
                f"JUDGE veto on constitutional grounds. Requires "
                f"supermajority (7/9) to override."
            )

        return conflict

    @classmethod
    def escalate_to_human(cls, conflict: Conflict, reason: str) -> Conflict:
        """Escalate an unresolvable conflict to the human sovereign."""
        conflict.resolution = ResolutionType.ESCALATED_TO_HUMAN
        conflict.resolution_note = (
            f"ESCALATED to human: {reason}. "
            f"Council cannot resolve internally. "
            f"Human decision required."
        )
        return conflict

    @classmethod
    def attempt_compromise(cls, positions: dict[AgentSeat, str]) -> Optional[str]:
        """Attempt to find a compromise between conflicting positions.

        Args:
            positions: Dict of agent_id -> their position description

        Returns:
            Compromise text if found, None if irreconcilable.
        """
        if len(positions) < 2:
            return None

        # Simple heuristic: if positions differ only in scope/approach,
        # suggest a phased approach
        if len(positions) == 2:
            return (
                "COMPROMISE: Phased approach — implement the minimal viable "
                "version first, gather evidence, then expand scope based on "
                "council review of phase 1 results."
            )

        return None


def resolve(conflict: Conflict) -> Conflict:
    """Resolve a conflict using the standard escalation ladder."""
    return ConflictResolver.handle_veto(
        veto_agent=conflict.parties[0] if conflict.parties else AgentSeat.CHAIRMAN,
        veto_reason=conflict.description,
    )
