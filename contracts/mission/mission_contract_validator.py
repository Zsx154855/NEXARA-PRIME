"""
Mission Contract Validator — cross-entry validation for agent role separation.

Enforces:
  1. Writer-Reviewer separation: no single agent holds both WRITER + REVIEWER
  2. Coordinator-Writer isolation for R2+ missions
  3. Unique agent_id across entries
  4. Dual permission conflict resolution (agent-level > mission-level)

This validator supplements JSON Schema structural validation with
semantic cross-entry rules that JSON Schema cannot express natively.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class AgentRole(str, Enum):
    WRITER = "WRITER"
    REVIEWER = "REVIEWER"
    COORDINATOR = "COORDINATOR"
    APPROVER = "APPROVER"
    SYSTEM = "SYSTEM"


@dataclass
class ValidationError:
    code: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


def validate_mission_contract(contract: dict[str, Any]) -> ValidationResult:
    """Validate a mission contract against cross-entry semantic rules.

    Args:
        contract: A dict conforming to mission_contract.schema.json.

    Returns:
        ValidationResult with errors for P1 violations, warnings for P2 issues.
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    agents: list[dict[str, Any]] = contract.get("agents", [])
    risk_level: str = contract.get("risk_level", "R0")
    writer_reviewer_sep: bool = contract.get("writer_reviewer_separation", True)
    coordinator_writer_iso: bool = contract.get("coordinator_writer_isolation", True)

    # ── Rule 1: Unique (agent_id, role) pairs ──
    # Same agent_id + same role = duplicate entry (not allowed)
    # Same agent_id + different role = cross-role assignment (checked by Rules 2-3)
    agent_ids = [a.get("agent_id", "") for a in agents]
    seen: set[tuple[str, str]] = set()
    for a in agents:
        aid = a.get("agent_id", "")
        role = a.get("role", "")
        if not aid:
            errors.append(ValidationError(
                code="MISSING_AGENT_ID",
                message="Agent entry missing agent_id",
                detail={"agents": agents},
            ))
        elif (aid, role) in seen:
            errors.append(ValidationError(
                code="DUPLICATE_AGENT_ID",
                message=f"Duplicate agent_id+role: {aid}/{role}",
                detail={"agent_id": aid, "role": role},
            ))
        seen.add((aid, role))

    # ── Rule 2: Writer-Reviewer separation (P1) ──
    roles_by_agent: dict[str, set[str]] = {}
    for a in agents:
        aid = a.get("agent_id", "")
        role = a.get("role", "")
        roles_by_agent.setdefault(aid, set()).add(role)

    if writer_reviewer_sep:
        for aid, roles in roles_by_agent.items():
            if AgentRole.WRITER in roles and AgentRole.REVIEWER in roles:
                errors.append(ValidationError(
                    code="P1_POLICY_VIOLATION_WRITER_REVIEWER_SEPARATION",
                    message=(
                        f"Agent '{aid}' holds both WRITER and REVIEWER roles. "
                        "Writer-Reviewer separation is required for audit integrity. "
                        "Set writer_reviewer_separation=false only for R0 self-review missions."
                    ),
                    detail={"agent_id": aid, "roles": list(roles)},
                ))

    # ── Rule 3: Coordinator-Writer isolation for R2+ (P2) ──
    risk_order = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}
    is_high_risk = risk_order.get(risk_level, 0) >= risk_order.get("R2", 2)

    if coordinator_writer_iso and is_high_risk:
        for aid, roles in roles_by_agent.items():
            if AgentRole.COORDINATOR in roles and AgentRole.WRITER in roles:
                errors.append(ValidationError(
                    code="P1_POLICY_VIOLATION_COORDINATOR_WRITER_ISOLATION",
                    message=(
                        f"Agent '{aid}' holds both COORDINATOR and WRITER roles "
                        f"on a {risk_level}-level mission. "
                        "Coordinator-Writer isolation is required for R2+ missions "
                        "to prevent orchestrator self-approval."
                    ),
                    detail={"agent_id": aid, "risk_level": risk_level, "roles": list(roles)},
                ))

    # ── Rule 4: Dual-permission conflict resolution (P2) ──
    permissions: list[dict[str, Any]] = contract.get("permissions", [])
    for perm in permissions:
        granted_to: list[str] = perm.get("granted_to", [])
        action = perm.get("action", "")
        for aid in granted_to:
            # Check if this agent's own permissions contradict mission-level
            agent_entry = next((a for a in agents if a.get("agent_id") == aid), None)
            if agent_entry:
                agent_perms: list[str] = agent_entry.get("permissions", [])
                # Agent claims a permission that mission-level denies
                # (Deny-by-default: agent-level WRITE doesn't override
                #  mission-level scope=FILE restriction)
                scope = perm.get("scope", "MISSION")
                if action in agent_perms and scope == "FILE":
                    warnings.append(ValidationError(
                        code="PERMISSION_SCOPE_RESTRICTION",
                        message=(
                            f"Agent '{aid}' has {action} permission restricted "
                            f"to scope={scope} by mission-level policy."
                        ),
                        detail={"agent_id": aid, "action": action, "scope": scope},
                    ))

    # ── Rule 5: APPROVER role warning (P2) ──
    approver_agents = [
        aid for aid, roles in roles_by_agent.items()
        if AgentRole.APPROVER in roles
    ]
    if approver_agents and is_high_risk:
        warnings.append(ValidationError(
            code="APPROVER_ROLE_ASSIGNED",
            message=(
                f"APPROVER role assigned to {approver_agents}. "
                "APPROVER is a distinct role from CTO. "
                "CTO approval is still required for NSEC Article 37 gates."
            ),
            detail={"approvers": approver_agents},
        ))

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def validate_mission_contract_from_file(path: str) -> ValidationResult:
    """Validate a mission contract JSON file."""
    import json
    with open(path) as f:
        contract = json.load(f)
    return validate_mission_contract(contract)


# ── Test fixtures ──

VALID_CONTRACT = {
    "mission_id": "mission_abc123def456",
    "objective": "Test mission with proper role separation",
    "scope": {
        "allowlist": ["contracts/*"],
        "denylist": ["src/nexara_prime/*"],
        "mutations": ["READ", "WRITE", "GENERATE_EVIDENCE"],
        "artifacts": ["EVIDENCE", "RECEIPT"],
        "gates": ["architecture_review"],
    },
    "agents": [
        {
            "agent_id": "hermes",
            "role": "WRITER",
            "capabilities": ["write_code", "run_tests"],
            "lease": {"duration_seconds": 3600, "renewable": True, "exclusivity": "EXCLUSIVE"},
            "permissions": ["READ", "WRITE", "EXECUTE_TEST", "GENERATE_EVIDENCE"],
        },
        {
            "agent_id": "claude",
            "role": "REVIEWER",
            "capabilities": ["read_code", "architecture_review"],
            "lease": {"duration_seconds": 1800, "renewable": False},
            "permissions": ["READ", "REVIEW", "BLOCK"],
        },
        {
            "agent_id": "agentos",
            "role": "COORDINATOR",
            "capabilities": ["orchestrate", "state_management"],
            "lease": {"duration_seconds": 7200, "renewable": True},
            "permissions": ["READ"],
        },
    ],
    "permissions": [],
    "writer_reviewer_separation": True,
    "coordinator_writer_isolation": True,
    "risk_level": "R2",
    "success_criteria": [
        {"criterion_id": "c1", "description": "Gate passes", "measurable": True, "verification": "GATE_PASS"},
    ],
    "required_evidence": [
        {"evidence_kind": "review", "produced_by": "REVIEWER", "verification_method": "REVIEW"},
    ],
    "approval_gate": {
        "required_approvals": 1,
        "approvers": ["cto"],
        "auto_approve_conditions": [],
    },
    "timeout": {"mission_timeout_seconds": 3600},
    "retry_policy": {"max_retries": 3},
}

INVALID_WRITER_REVIEWER_CONTRACT = {
    **VALID_CONTRACT,
    "agents": [
        {
            "agent_id": "hermes",
            "role": "WRITER",
            "capabilities": ["write_code"],
            "lease": {"duration_seconds": 3600, "renewable": True},
            "permissions": ["READ", "WRITE"],
        },
        {
            "agent_id": "hermes",  # SAME AGENT
            "role": "REVIEWER",
            "capabilities": ["read_code"],
            "lease": {"duration_seconds": 1800, "renewable": False},
            "permissions": ["READ", "REVIEW"],
        },
    ],
}

INVALID_COORDINATOR_WRITER_CONTRACT = {
    **VALID_CONTRACT,
    "risk_level": "R3",
    "agents": [
        {
            "agent_id": "hermes",
            "role": "WRITER",
            "capabilities": ["write_code"],
            "lease": {"duration_seconds": 3600, "renewable": True, "exclusivity": "EXCLUSIVE"},
            "permissions": ["READ", "WRITE"],
        },
        {
            "agent_id": "hermes",  # SAME AGENT as COORDINATOR+WRITER on R3
            "role": "COORDINATOR",
            "capabilities": ["orchestrate"],
            "lease": {"duration_seconds": 7200, "renewable": True},
            "permissions": ["READ"],
        },
    ],
}

DUPLICATE_AGENT_ID_CONTRACT = {
    **VALID_CONTRACT,
    "agents": [
        {
            "agent_id": "hermes",
            "role": "WRITER",
            "capabilities": ["write_code"],
            "lease": {"duration_seconds": 3600, "renewable": True},
            "permissions": ["READ", "WRITE"],
        },
        {
            "agent_id": "claude",
            "role": "REVIEWER",
            "capabilities": ["read_code"],
            "lease": {"duration_seconds": 1800, "renewable": False},
            "permissions": ["READ", "REVIEW"],
        },
        {
            "agent_id": "hermes",  # DUPLICATE: same agent_id + same role WRITER
            "role": "WRITER",
            "capabilities": ["write_code"],
            "lease": {"duration_seconds": 3600, "renewable": True},
            "permissions": ["READ", "WRITE"],
        },
    ],
}
