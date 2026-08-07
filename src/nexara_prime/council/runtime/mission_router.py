"""NEXARA Council V2 — Mission Router

Routes missions to the appropriate agents based on mission type,
risk level, and agent availability. Integrates with the existing
NexaraRuntime and Governance systems.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from nexara_prime.council.mission_dna import MissionDNA, MissionRisk


class AgentSeat(str, Enum):
    """Council seats."""
    CHAIRMAN = "H-CHAIRMAN"
    STAFF = "H-STAFF"
    ARCH = "H-ARCH"
    CODE = "H-CODE"
    EXEC = "H-EXEC"
    RED = "H-RED"
    JUDGE = "H-JUDGE"
    MEM = "H-MEM"
    TOKEN = "H-TOKEN"


class RoutingStrategy(str, Enum):
    """How to route a mission."""
    FULL_COUNCIL = "FULL_COUNCIL"       # All 9 seats
    TRIAD = "TRIAD"                     # 3 seats
    SOLO = "SOLO"                       # 1 seat
    URGENT = "URGENT"                   # Chairman + 2


@dataclass
class RoutingDecision:
    """Result of mission routing."""
    mission_id: str
    strategy: RoutingStrategy
    assigned_seats: list[AgentSeat]
    excluded_seats: list[AgentSeat] = field(default_factory=list)
    rationale: str = ""
    routing_id: str = field(default_factory=lambda: f"rtr-{uuid.uuid4().hex[:8]}")


class MissionRouter:
    """Routes missions to council agents based on mission characteristics.

    Integrates with:
    - NexaraRuntime for mission state
    - ApprovalPolicy for level-based routing
    - TokenGovernor for budget-aware routing
    """

    # Minimum seats per mission type
    _TYPE_REQUIREMENTS: dict[str, tuple[list[AgentSeat], RoutingStrategy]] = {
        "ARCHITECTURE": ([AgentSeat.CHAIRMAN, AgentSeat.ARCH, AgentSeat.CODE], RoutingStrategy.TRIAD),
        "IMPLEMENTATION": ([AgentSeat.CHAIRMAN, AgentSeat.CODE, AgentSeat.ARCH], RoutingStrategy.TRIAD),
        "SECURITY_AUDIT": ([AgentSeat.RED, AgentSeat.JUDGE, AgentSeat.CHAIRMAN], RoutingStrategy.TRIAD),
        "GOVERNANCE": ([AgentSeat.JUDGE, AgentSeat.CHAIRMAN, AgentSeat.STAFF], RoutingStrategy.TRIAD),
        "DEPLOYMENT": ([AgentSeat.CHAIRMAN, AgentSeat.EXEC, AgentSeat.RED, AgentSeat.JUDGE, AgentSeat.CODE],
                       RoutingStrategy.FULL_COUNCIL),
        "CONSTITUTIONAL": (list(AgentSeat), RoutingStrategy.FULL_COUNCIL),
        "ROUTINE": ([AgentSeat.CODE], RoutingStrategy.SOLO),
        "URGENT": ([AgentSeat.CHAIRMAN, AgentSeat.STAFF, AgentSeat.EXEC], RoutingStrategy.URGENT),
    }

    @classmethod
    def route(cls, dna: MissionDNA) -> RoutingDecision:
        """Determine the routing strategy for a mission.

        Args:
            dna: The Mission DNA to route.

        Returns:
            RoutingDecision with assigned seats and strategy.
        """
        # Determine mission type from DNA objective
        mission_type = cls._classify_mission(dna)

        # Get base requirements
        required_seats, strategy = cls._TYPE_REQUIREMENTS.get(
            mission_type,
            ([AgentSeat.CHAIRMAN, AgentSeat.STAFF, AgentSeat.CODE], RoutingStrategy.TRIAD),
        )

        # Escalate based on risk
        assigned = list(required_seats)
        if dna.risk >= MissionRisk.R3_HIGH:
            if AgentSeat.RED not in assigned:
                assigned.append(AgentSeat.RED)
            if AgentSeat.JUDGE not in assigned:
                assigned.append(AgentSeat.JUDGE)
            if len(assigned) >= 5:
                strategy = RoutingStrategy.FULL_COUNCIL

        if dna.risk >= MissionRisk.R4_CRITICAL:
            assigned = list(AgentSeat)  # All seats
            strategy = RoutingStrategy.FULL_COUNCIL

        # Always include TOKEN for budget tracking
        if AgentSeat.TOKEN not in assigned:
            assigned.append(AgentSeat.TOKEN)

        # Always include MEM for evidence
        if AgentSeat.MEM not in assigned:
            assigned.append(AgentSeat.MEM)

        # Build routing decision
        all_seats = list(AgentSeat)
        excluded = [s for s in all_seats if s not in assigned]

        routing_id = hashlib.sha256(
            f"{dna.mission_id}:{strategy.value}:{','.join(sorted(s.value for s in assigned))}".encode()
        ).hexdigest()[:16]

        return RoutingDecision(
            mission_id=dna.mission_id,
            strategy=strategy,
            assigned_seats=assigned,
            excluded_seats=excluded,
            rationale=f"Mission type={mission_type}, risk={dna.risk.name}, {len(assigned)} seats assigned",
            routing_id=f"rtr-{routing_id}",
        )

    @classmethod
    def _classify_mission(cls, dna: MissionDNA) -> str:
        """Classify mission type from DNA objective and constraints."""
        objective_lower = dna.objective.lower()

        type_keywords = {
            "ARCHITECTURE": ["architecture", "design", "system boundary", "refactor", "restructure"],
            "SECURITY_AUDIT": ["security", "audit", "vulnerability", "penetration", "red team", "threat"],
            "GOVERNANCE": ["governance", "policy", "nsec", "constitution", "compliance", "approval"],
            "DEPLOYMENT": ["deploy", "release", "production", "publish", "ship"],
            "CONSTITUTIONAL": ["constitutional", "amend", "amendment", "council restructure"],
        }

        for mtype, keywords in type_keywords.items():
            if any(kw in objective_lower for kw in keywords):
                return mtype

        if "implement" in objective_lower or "build" in objective_lower or "code" in objective_lower:
            return "IMPLEMENTATION"

        if dna.risk >= MissionRisk.R3_HIGH:
            return "DEPLOYMENT"

        return "ROUTINE"


# Module-level convenience
def route_mission(dna: MissionDNA) -> RoutingDecision:
    """Route a mission through the council. Convenience function."""
    return MissionRouter.route(dna)
