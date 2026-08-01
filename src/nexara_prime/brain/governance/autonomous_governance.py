"""Autonomous Governance Layer — authority engine, approval orchestrator, policy runtime.

Inherits R0-R4 Risk Model. Enforces: Mission→Risk→Authority→Approval→Execution.

FAIL-CLOSED SEMANTICS (v2):
  R0, R1: AUTO — authorized if no conflicts.
  R2, R3: REQUIRE an explicit, matching, non-expired, non-revoked APPROVED decision.
           Default: authorized=false, allowed=false, can_execute=false.
  R4:      BLOCKED — always denied; requires explicit human sovereign approval
           outside the automated system.

Key distinction:
  can_plan / can_dry_run → allowed (planning is safe)
  can_execute             → requires approved decision for R2+
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexara_prime.models import now_iso, new_id


class ApprovalLevel(str, Enum):
    AUTO = "auto"
    NOTIFY = "notify"
    CONFIRM = "confirm"
    HUMAN = "human"
    BLOCKED = "blocked"


class DecisionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"
    EXPIRED = "expired"
    CONSUMED = "consumed"


RISK_APPROVAL_MAP: dict[str, ApprovalLevel] = {
    "R0": ApprovalLevel.AUTO,
    "R1": ApprovalLevel.AUTO,
    "R2": ApprovalLevel.CONFIRM,
    "R3": ApprovalLevel.HUMAN,
    "R4": ApprovalLevel.BLOCKED,
}

# R2+ REQUIRE approval — fail closed by default
REQUIRES_APPROVAL: set[str] = {"R2", "R3", "R4"}


class AuthorityEngine:
    """Determines whether an action is authorized based on risk and agent identity.

    FAIL-CLOSED: R2/R3/R4 return authorized=False by default.
    Only R0/R1 return authorized=True (auto-approved for read-only/reversible ops).
    """

    def authorize(self, risk_level: str, agent_role: str, action: str) -> dict[str, Any]:
        approval = RISK_APPROVAL_MAP.get(risk_level, ApprovalLevel.CONFIRM)
        if approval == ApprovalLevel.BLOCKED:
            return {
                "risk_level": risk_level, "agent_role": agent_role, "action": action,
                "approval_level": approval.value, "authorized": False,
                "can_plan": False, "can_dry_run": False, "can_execute": False,
                "requires_human": True, "requires_confirmation": True,
                "reason": "R4_blocked_permanently",
            }
        if risk_level in REQUIRES_APPROVAL:
            # FAIL-CLOSED: planning/dry-run allowed, execution requires approved decision
            return {
                "risk_level": risk_level, "agent_role": agent_role, "action": action,
                "approval_level": approval.value, "authorized": False,
                "can_plan": True, "can_dry_run": True, "can_execute": False,
                "requires_human": approval == ApprovalLevel.HUMAN,
                "requires_confirmation": True,
                "reason": "requires_approved_decision",
            }
        # R0, R1: auto-approved
        return {
            "risk_level": risk_level, "agent_role": agent_role, "action": action,
            "approval_level": approval.value, "authorized": True,
            "can_plan": True, "can_dry_run": True, "can_execute": True,
            "requires_human": False, "requires_confirmation": False,
            "reason": "auto_approved_low_risk",
        }


@dataclass
class ApprovalDecision:
    decision_id: str
    mission_id: str
    project_id: str
    risk_level: str
    action: str
    resource: str
    scope: str
    approval_level: ApprovalLevel
    status: DecisionStatus = DecisionStatus.PENDING
    authorized: bool = False
    reason: str = ""
    approved_by: str = ""
    approved_at: str = ""
    issued_at: str = field(default_factory=now_iso)
    expires_at: str = ""
    evidence_id: str = ""
    nonce: str = field(default_factory=lambda: new_id("nonce"))

    def is_valid(self) -> bool:
        """Check if this decision is currently valid for execution."""
        if self.status != DecisionStatus.APPROVED:
            return False
        if self.expires_at and self.expires_at < now_iso():
            return False
        return True


class ApprovalOrchestrator:
    """Orchestrates approval workflow for autonomous actions.

    FAIL-CLOSED: request() creates a PENDING decision (authorized=False).
    Only an explicit approve() call transitions to APPROVED (authorized=True).
    reject() transitions to REJECTED. revoke() to REVOKED.
    consume() marks as CONSUMED (one-time use).

    Verify requires: matching action, resource, mission_id, project_id,
    non-expired, non-revoked, non-consumed, status=APPROVED.
    """

    def __init__(self) -> None:
        self._decisions: dict[str, ApprovalDecision] = {}
        self._pending: list[str] = []

    def request(
        self,
        mission_id: str,
        project_id: str,
        risk_level: str,
        action: str,
        resource: str = "*",
        scope: str = "local",
    ) -> ApprovalDecision:
        """Create a PENDING approval request. FAIL-CLOSED: authorized=False."""
        approval = RISK_APPROVAL_MAP.get(risk_level, ApprovalLevel.CONFIRM)
        did = new_id("dec")
        d = ApprovalDecision(
            decision_id=did,
            mission_id=mission_id,
            project_id=project_id,
            risk_level=risk_level,
            action=action,
            resource=resource,
            scope=scope,
            approval_level=approval,
            status=DecisionStatus.PENDING,
            authorized=False,
            reason="pending_approval",
        )
        self._decisions[did] = d
        if approval in (ApprovalLevel.CONFIRM, ApprovalLevel.HUMAN):
            self._pending.append(did)
        return d

    def approve(self, decision_id: str, approved_by: str = "human") -> ApprovalDecision | None:
        d = self._decisions.get(decision_id)
        if d is None:
            return None
        updated = ApprovalDecision(
            decision_id=d.decision_id,
            mission_id=d.mission_id,
            project_id=d.project_id,
            risk_level=d.risk_level,
            action=d.action,
            resource=d.resource,
            scope=d.scope,
            approval_level=d.approval_level,
            status=DecisionStatus.APPROVED,
            authorized=True,
            reason="approved",
            approved_by=approved_by,
            approved_at=now_iso(),
            issued_at=d.issued_at,
            expires_at=d.expires_at,
            evidence_id=d.evidence_id,
            nonce=d.nonce,
        )
        self._decisions[decision_id] = updated
        if decision_id in self._pending:
            self._pending.remove(decision_id)
        return updated

    def reject(self, decision_id: str, reason: str = "rejected") -> ApprovalDecision | None:
        d = self._decisions.get(decision_id)
        if d is None:
            return None
        updated = ApprovalDecision(
            decision_id=d.decision_id, mission_id=d.mission_id, project_id=d.project_id,
            risk_level=d.risk_level, action=d.action, resource=d.resource, scope=d.scope,
            approval_level=d.approval_level, status=DecisionStatus.REJECTED,
            authorized=False, reason=reason, issued_at=d.issued_at, nonce=d.nonce,
        )
        self._decisions[decision_id] = updated
        if decision_id in self._pending:
            self._pending.remove(decision_id)
        return updated

    def revoke(self, decision_id: str) -> ApprovalDecision | None:
        d = self._decisions.get(decision_id)
        if d is None:
            return None
        updated = ApprovalDecision(
            decision_id=d.decision_id, mission_id=d.mission_id, project_id=d.project_id,
            risk_level=d.risk_level, action=d.action, resource=d.resource, scope=d.scope,
            approval_level=d.approval_level, status=DecisionStatus.REVOKED,
            authorized=False, reason="revoked", issued_at=d.issued_at, nonce=d.nonce,
        )
        self._decisions[decision_id] = updated
        return updated

    def consume(self, decision_id: str) -> ApprovalDecision | None:
        """Mark a decision as consumed (one-time use)."""
        d = self._decisions.get(decision_id)
        if d is None or not d.is_valid():
            return None
        updated = ApprovalDecision(
            decision_id=d.decision_id, mission_id=d.mission_id, project_id=d.project_id,
            risk_level=d.risk_level, action=d.action, resource=d.resource, scope=d.scope,
            approval_level=d.approval_level, status=DecisionStatus.CONSUMED,
            authorized=True, reason="consumed", approved_by=d.approved_by,
            approved_at=d.approved_at, issued_at=d.issued_at,
            expires_at=d.expires_at, evidence_id=d.evidence_id, nonce=d.nonce,
        )
        self._decisions[decision_id] = updated
        return updated

    def verify(
        self,
        decision_id: str,
        *,
        mission_id: str,
        project_id: str,
        action: str,
        resource: str = "*",
    ) -> dict[str, Any]:
        """Verify an approval decision is valid for execution. FAIL-CLOSED."""
        d = self._decisions.get(decision_id)
        if d is None:
            return {"valid": False, "authorized": False, "reason": "decision_not_found"}

        # Fail-closed: any mismatch = denied
        if not d.is_valid():
            return {"valid": False, "authorized": False, "reason": f"decision_not_valid: status={d.status.value}"}
        if d.mission_id != mission_id:
            return {"valid": False, "authorized": False, "reason": "mission_id_mismatch"}
        if d.project_id != project_id:
            return {"valid": False, "authorized": False, "reason": "project_id_mismatch"}
        if d.action != action:
            return {"valid": False, "authorized": False, "reason": "action_mismatch"}
        if d.resource != resource and d.resource != "*":
            return {"valid": False, "authorized": False, "reason": "resource_mismatch"}

        return {
            "valid": True,
            "authorized": True,
            "decision_id": d.decision_id,
            "mission_id": d.mission_id,
            "action": d.action,
            "nonce": d.nonce,
        }

    def pending(self) -> list[ApprovalDecision]:
        return [self._decisions[did] for did in self._pending]

    def stats(self) -> dict[str, Any]:
        total = len(self._decisions)
        if total == 0:
            return {"total": 0, "approved": 0, "rejected": 0, "pending": 0, "revoked": 0, "consumed": 0}
        return {
            "total": total,
            "approved": sum(1 for d in self._decisions.values() if d.status == DecisionStatus.APPROVED),
            "rejected": sum(1 for d in self._decisions.values() if d.status == DecisionStatus.REJECTED),
            "pending": len(self._pending),
            "revoked": sum(1 for d in self._decisions.values() if d.status == DecisionStatus.REVOKED),
            "consumed": sum(1 for d in self._decisions.values() if d.status == DecisionStatus.CONSUMED),
        }


class PolicyRuntime:
    """Runtime policy enforcement — checks every action against governance rules.

    FAIL-CLOSED: R2+ requires a verified approved decision.
    Default allowed=False unless auto-approved (R0/R1) or decision-bound.
    """

    def __init__(self) -> None:
        self._violations: list[dict[str, Any]] = []
        self._orchestrator: ApprovalOrchestrator | None = None

    def bind_orchestrator(self, orch: ApprovalOrchestrator) -> None:
        self._orchestrator = orch

    def enforce(
        self,
        risk_level: str,
        action: str,
        allowed_actions: list[str],
        forbidden_actions: list[str],
        *,
        decision_id: str | None = None,
        mission_id: str = "",
        project_id: str = "",
        resource: str = "*",
    ) -> dict[str, Any]:
        """Enforce policy. FAIL-CLOSED for R2+ without valid decision."""
        # Forbidden actions always blocked
        if action in forbidden_actions:
            self._violations.append({
                "risk": risk_level, "action": action, "result": "BLOCKED",
                "reason": "forbidden_action", "timestamp": now_iso(),
            })
            return {"allowed": False, "reason": "forbidden_action"}

        # Not in allowed actions → blocked
        if action not in allowed_actions:
            self._violations.append({
                "risk": risk_level, "action": action, "result": "BLOCKED",
                "reason": "not_allowed", "timestamp": now_iso(),
            })
            return {"allowed": False, "reason": "not_allowed"}

        approval = RISK_APPROVAL_MAP.get(risk_level, ApprovalLevel.CONFIRM)

        # R4: always blocked
        if approval == ApprovalLevel.BLOCKED:
            self._violations.append({
                "risk": risk_level, "action": action, "result": "BLOCKED",
                "reason": "R4_blocked", "timestamp": now_iso(),
            })
            return {"allowed": False, "reason": "R4_blocked"}

        # R2, R3: require verified approved decision
        if risk_level in REQUIRES_APPROVAL:
            if decision_id is None:
                return {"allowed": False, "reason": "missing_decision_id", "approval_level": approval.value}
            if self._orchestrator is None:
                return {"allowed": False, "reason": "orchestrator_not_bound", "approval_level": approval.value}
            result = self._orchestrator.verify(
                decision_id, mission_id=mission_id, project_id=project_id,
                action=action, resource=resource,
            )
            if not result["valid"]:
                self._violations.append({
                    "risk": risk_level, "action": action, "result": "BLOCKED",
                    "reason": result["reason"], "timestamp": now_iso(),
                })
                return {"allowed": False, "reason": result["reason"], "approval_level": approval.value}
            return {"allowed": True, "approval_level": approval.value, "decision_id": decision_id}

        # R0, R1: auto-approved
        return {"allowed": True, "approval_level": approval.value}

    def violations(self) -> list[dict[str, Any]]:
        return list(self._violations)
