"""NEXARA Council V2 — Mission DNA

Every mission entering the Council must be assigned a Mission DNA — a structured
declaration of objective, constraints, agents, tools, permissions, expected output,
verification criteria, and rollback plan.

No mission proceeds without DNA. This is the entry contract for the Council pipeline.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MissionRisk(str, Enum):
    """Mission risk classification aligned with risk_policy.yaml."""
    R0_NEGLIGIBLE = "R0_NEGLIGIBLE"
    R1_LOW = "R1_LOW"
    R2_MODERATE = "R2_MODERATE"
    R3_HIGH = "R3_HIGH"
    R4_CRITICAL = "R4_CRITICAL"


class DNAStatus(str, Enum):
    """Mission DNA lifecycle status."""
    DRAFT = "DRAFT"            # Being created
    GENERATED = "GENERATED"    # DNA complete, awaiting council
    DELIBERATING = "DELIBERATING"  # Council is discussing
    APPROVED = "APPROVED"      # Council approved
    REJECTED = "REJECTED"      # Council rejected
    EXECUTING = "EXECUTING"    # Pipeline executing
    COMPLETED = "COMPLETED"    # Mission done
    ROLLED_BACK = "ROLLED_BACK"  # Rolled back


@dataclass
class MissionDNA:
    """The DNA of a council mission — its complete specification.

    This is the contract that all council agents must honor.
    Once approved, only the Chairman can modify specific fields
    (with council review).

    Required fields per council_rules.yaml §pipeline.stages[1].required_fields:
    - mission_id
    - objective
    - constraints
    - agents
    - tools
    - permissions
    - expected_output
    - verification
    - rollback
    """

    # === Required Fields ===

    mission_id: str = field(default_factory=lambda: f"mis-{uuid.uuid4().hex[:12]}")
    """Unique mission identifier."""

    objective: str = ""
    """What this mission must accomplish. One sentence, testable."""

    constraints: list[str] = field(default_factory=list)
    """Hard constraints that must not be violated."""

    agents: list[str] = field(default_factory=list)
    """Council agents assigned to this mission."""

    tools: list[str] = field(default_factory=list)
    """Tools authorized for this mission."""

    permissions: list[str] = field(default_factory=list)
    """Explicit permissions granted (read, write, execute, deploy)."""

    expected_output: str = ""
    """Concrete, verifiable description of the expected output."""

    verification: list[str] = field(default_factory=list)
    """How to verify the mission was completed successfully."""

    rollback: list[str] = field(default_factory=list)
    """Steps to roll back if the mission fails or is rejected."""

    # === Optional Fields ===

    risk: MissionRisk = MissionRisk.R1_LOW
    """Risk classification."""

    approval_level: str = "L1_STANDARD"
    """Approval level from approval_policy.yaml."""

    deadline: Optional[str] = None
    """ISO8601 deadline if time-bound."""

    parent_mission_id: Optional[str] = None
    """Parent mission if this is a sub-mission."""

    evidence_refs: list[str] = field(default_factory=list)
    """References to existing evidence supporting this mission."""

    status: DNAStatus = DNAStatus.DRAFT
    """Current lifecycle status."""

    dna_hash: str = ""
    """SHA256 hash of DNA content for integrity verification."""

    created_at: str = ""
    """ISO8601 creation timestamp."""

    created_by: str = "H-STAFF"
    """Which agent created this DNA."""

    # === Computed Fields ===

    @property
    def is_complete(self) -> bool:
        """Check if all required fields are populated."""
        required = [
            bool(self.mission_id),
            bool(self.objective),
            bool(self.constraints),
            bool(self.agents),
            bool(self.tools),
            bool(self.permissions),
            bool(self.expected_output),
            bool(self.verification),
            bool(self.rollback),
        ]
        return all(required)

    @property
    def missing_fields(self) -> list[str]:
        """List required fields that are empty."""
        field_map = {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "constraints": self.constraints,
            "agents": self.agents,
            "tools": self.tools,
            "permissions": self.permissions,
            "expected_output": self.expected_output,
            "verification": self.verification,
            "rollback": self.rollback,
        }
        return [name for name, val in field_map.items() if not val]

    def compute_hash(self) -> str:
        """Compute SHA256 hash of the DNA for integrity verification."""
        content = (
            f"{self.mission_id}|{self.objective}|"
            f"{'|'.join(sorted(self.constraints))}|"
            f"{'|'.join(sorted(self.agents))}|"
            f"{'|'.join(sorted(self.tools))}|"
            f"{'|'.join(sorted(self.permissions))}|"
            f"{self.expected_output}|"
            f"{'|'.join(self.verification)}|"
            f"{'|'.join(self.rollback)}"
        )
        self.dna_hash = hashlib.sha256(content.encode()).hexdigest()
        return self.dna_hash

    def to_dict(self) -> dict:
        """Serialize to dict for JSON persistence."""
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "constraints": self.constraints,
            "agents": self.agents,
            "tools": self.tools,
            "permissions": self.permissions,
            "expected_output": self.expected_output,
            "verification": self.verification,
            "rollback": self.rollback,
            "risk": self.risk.value,
            "approval_level": self.approval_level,
            "deadline": self.deadline,
            "parent_mission_id": self.parent_mission_id,
            "evidence_refs": self.evidence_refs,
            "status": self.status.value,
            "dna_hash": self.dna_hash,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MissionDNA:
        """Deserialize from dict."""
        dna = cls(
            mission_id=data.get("mission_id", ""),
            objective=data.get("objective", ""),
            constraints=data.get("constraints", []),
            agents=data.get("agents", []),
            tools=data.get("tools", []),
            permissions=data.get("permissions", []),
            expected_output=data.get("expected_output", ""),
            verification=data.get("verification", []),
            rollback=data.get("rollback", []),
            risk=MissionRisk(data.get("risk", "R1_LOW")),
            approval_level=data.get("approval_level", "L1_STANDARD"),
            deadline=data.get("deadline"),
            parent_mission_id=data.get("parent_mission_id"),
            evidence_refs=data.get("evidence_refs", []),
            status=DNAStatus(data.get("status", "DRAFT")),
            dna_hash=data.get("dna_hash", ""),
            created_at=data.get("created_at", ""),
            created_by=data.get("created_by", "H-STAFF"),
        )
        return dna

    def __repr__(self) -> str:
        return (
            f"MissionDNA(id={self.mission_id}, "
            f"objective={self.objective[:60]}..., "
            f"risk={self.risk.value}, "
            f"status={self.status.value})"
        )


# Builder pattern for convenient DNA creation
class DNABuilder:
    """Fluent builder for MissionDNA."""

    def __init__(self) -> None:
        self._dna = MissionDNA()

    def with_objective(self, objective: str) -> DNABuilder:
        self._dna.objective = objective
        return self

    def with_constraints(self, *constraints: str) -> DNABuilder:
        self._dna.constraints = list(constraints)
        return self

    def with_agents(self, *agents: str) -> DNABuilder:
        self._dna.agents = list(agents)
        return self

    def with_tools(self, *tools: str) -> DNABuilder:
        self._dna.tools = list(tools)
        return self

    def with_permissions(self, *permissions: str) -> DNABuilder:
        self._dna.permissions = list(permissions)
        return self

    def with_expected_output(self, output: str) -> DNABuilder:
        self._dna.expected_output = output
        return self

    def with_verification(self, *steps: str) -> DNABuilder:
        self._dna.verification = list(steps)
        return self

    def with_rollback(self, *steps: str) -> DNABuilder:
        self._dna.rollback = list(steps)
        return self

    def with_risk(self, risk: MissionRisk) -> DNABuilder:
        self._dna.risk = risk
        return self

    def with_approval_level(self, level: str) -> DNABuilder:
        self._dna.approval_level = level
        return self

    def build(self) -> MissionDNA:
        """Build and validate the DNA. Raises ValueError if incomplete."""
        dna = self._dna
        if not dna.is_complete:
            raise ValueError(
                f"MissionDNA incomplete. Missing fields: {dna.missing_fields}"
            )
        dna.compute_hash()
        dna.status = DNAStatus.GENERATED
        from datetime import datetime, timezone
        dna.created_at = datetime.now(timezone.utc).isoformat()
        return dna
