"""Agent Role Constraint Validator — enforces writer_reviewer_separation
and coordinator_writer_isolation rules.

Part of NEXARA Agent Mission Lifecycle Manager Phase 1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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


# ── Role enum ──

VALID_ROLES = frozenset({"WRITER", "REVIEWER", "COORDINATOR", "APPROVER", "VERIFIER", "SYSTEM"})
HUMAN_ONLY_ROLES = frozenset({"APPROVER"})

RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}


def _risk_ge(level: str, threshold: str) -> bool:
    return RISK_ORDER.get(level, 0) >= RISK_ORDER.get(threshold, 0)


def validate_agent_roles(
    agents: list[dict[str, Any]],
    risk_level: str = "R0",
    *,
    writer_reviewer_separation: bool = True,
    coordinator_writer_isolation: bool = True,
) -> ValidationResult:
    """Validate agent role assignments for a mission.

    Rules:
      1. Each agent entry must have a valid role from VALID_ROLES.
      2. No (agent_id, role) pair may appear more than once.
      3. When writer_reviewer_separation=True, no agent may hold both
         WRITER and REVIEWER.
      4. When coordinator_writer_isolation=True AND risk_level >= R2,
         no agent may hold both COORDINATOR and WRITER.
      5. APPROVER role is human-only — AI_MODEL/SYSTEM agents cannot
         hold APPROVER.

    Args:
        agents: List of agent dicts with keys: agent_id, role, agent_type.
        risk_level: Mission risk level (R0-R4).
        writer_reviewer_separation: Enforce WRITER != REVIEWER per agent.
        coordinator_writer_isolation: Enforce COORDINATOR != WRITER per
            agent for R2+ missions.

    Returns:
        ValidationResult — valid=True iff no P1 violations found.
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    role_map: dict[str, set[str]] = {}  # agent_id → {roles}
    seen_pairs: set[tuple[str, str]] = set()  # (agent_id, role)

    for a in agents:
        aid = str(a.get("agent_id", "")).strip()
        role = str(a.get("role", "")).strip().upper()
        agent_type = str(a.get("agent_type", "AI_MODEL")).strip()

        # Rule 1: valid role
        if role not in VALID_ROLES:
            errors.append(ValidationError(
                code="INVALID_ROLE",
                message=f"Agent '{aid}' has invalid role '{role}'. Must be one of {sorted(VALID_ROLES)}.",
                detail={"agent_id": aid, "role": role},
            ))
            continue

        # Rule 1b: human-only roles
        if role in HUMAN_ONLY_ROLES and agent_type != "HUMAN":
            errors.append(ValidationError(
                code="P1_POLICY_VIOLATION_APPROVER_NOT_HUMAN",
                message=(
                    f"Agent '{aid}' holds APPROVER role but agent_type='{agent_type}'. "
                    "APPROVER role is reserved for HUMAN agents (CTO)."
                ),
                detail={"agent_id": aid, "role": role, "agent_type": agent_type},
            ))

        # Rule 2: duplicate (agent_id, role)
        if (aid, role) in seen_pairs:
            errors.append(ValidationError(
                code="DUPLICATE_AGENT_ROLE",
                message=f"Duplicate assignment: agent '{aid}' already has role '{role}'.",
                detail={"agent_id": aid, "role": role},
            ))
            continue
        seen_pairs.add((aid, role))

        # Build role map for cross-role checks
        role_map.setdefault(aid, set()).add(role)

    # Rule 3: writer ≠ reviewer
    if writer_reviewer_separation:
        for aid, roles in role_map.items():
            if "WRITER" in roles and "REVIEWER" in roles:
                errors.append(ValidationError(
                    code="P1_POLICY_VIOLATION_WRITER_REVIEWER_SEPARATION",
                    message=(
                        f"Agent '{aid}' holds both WRITER and REVIEWER roles. "
                        "Independent review requires separate agents for writing and reviewing."
                    ),
                    detail={"agent_id": aid, "roles": sorted(roles)},
                ))

    # Rule 4: coordinator ≠ writer for R2+
    if coordinator_writer_isolation and _risk_ge(risk_level, "R2"):
        for aid, roles in role_map.items():
            if "COORDINATOR" in roles and "WRITER" in roles:
                errors.append(ValidationError(
                    code="P1_POLICY_VIOLATION_COORDINATOR_WRITER_ISOLATION",
                    message=(
                        f"Agent '{aid}' holds both COORDINATOR and WRITER roles "
                        f"on a {risk_level} mission. R2+ missions require separate "
                        "coordinator and writer to prevent orchestrator self-approval."
                    ),
                    detail={"agent_id": aid, "risk_level": risk_level, "roles": sorted(roles)},
                ))

    # Rule 5: APPROVER role warning (not blocking — CTO always has final say)
    approver_agents = [aid for aid, roles in role_map.items() if "APPROVER" in roles]
    if approver_agents and _risk_ge(risk_level, "R2"):
        warnings.append(ValidationError(
            code="APPROVER_ROLE_ASSIGNED_HIGH_RISK",
            message=(
                f"APPROVER role assigned to {approver_agents} on {risk_level} mission. "
                "NSEC Article 37 CTO approval is still required for merge/deploy."
            ),
            detail={"approvers": approver_agents, "risk_level": risk_level},
        ))

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
