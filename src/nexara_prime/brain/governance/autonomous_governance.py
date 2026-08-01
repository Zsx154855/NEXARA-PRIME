"""Autonomous Governance Layer — authority engine, approval orchestrator, policy runtime.

Inherits R0-R4 Risk Model. Enforces: Mission→Risk→Authority→Approval→Execution.
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


RISK_APPROVAL_MAP: dict[str, ApprovalLevel] = {
    "R0": ApprovalLevel.AUTO,
    "R1": ApprovalLevel.AUTO,
    "R2": ApprovalLevel.CONFIRM,
    "R3": ApprovalLevel.HUMAN,
    "R4": ApprovalLevel.BLOCKED,
}


class AuthorityEngine:
    """Determines whether an action is authorized based on risk and agent identity."""

    def authorize(self, risk_level: str, agent_role: str, action: str) -> dict[str, Any]:
        approval = RISK_APPROVAL_MAP.get(risk_level, ApprovalLevel.CONFIRM)
        authorized = approval != ApprovalLevel.BLOCKED
        return {"risk_level": risk_level, "agent_role": agent_role, "action": action,
                "approval_level": approval.value, "authorized": authorized,
                "requires_human": approval == ApprovalLevel.HUMAN,
                "requires_confirmation": approval in (ApprovalLevel.CONFIRM, ApprovalLevel.HUMAN)}


@dataclass
class ApprovalDecision:
    decision_id: str
    mission_id: str
    risk_level: str
    action: str
    approval_level: ApprovalLevel
    authorized: bool
    reason: str = ""
    approved_by: str = ""
    approved_at: str = ""


class ApprovalOrchestrator:
    """Orchestrates approval workflow for autonomous actions."""

    def __init__(self) -> None:
        self._decisions: dict[str, ApprovalDecision] = {}
        self._pending: list[str] = []

    def request(self, mission_id: str, risk_level: str, action: str) -> ApprovalDecision:
        approval = RISK_APPROVAL_MAP.get(risk_level, ApprovalLevel.CONFIRM)
        did = new_id("dec")
        d = ApprovalDecision(did, mission_id, risk_level, action, approval, approval != ApprovalLevel.BLOCKED)
        self._decisions[did] = d
        if approval in (ApprovalLevel.CONFIRM, ApprovalLevel.HUMAN):
            self._pending.append(did)
        return d

    def approve(self, decision_id: str, approved_by: str = "system") -> ApprovalDecision | None:
        d = self._decisions.get(decision_id)
        if d is None:
            return None
        updated = ApprovalDecision(d.decision_id, d.mission_id, d.risk_level, d.action, d.approval_level, True, "approved", approved_by, now_iso())
        self._decisions[decision_id] = updated
        if decision_id in self._pending:
            self._pending.remove(decision_id)
        return updated

    def reject(self, decision_id: str, reason: str = "rejected") -> ApprovalDecision | None:
        d = self._decisions.get(decision_id)
        if d is None:
            return None
        updated = ApprovalDecision(d.decision_id, d.mission_id, d.risk_level, d.action, d.approval_level, False, reason)
        self._decisions[decision_id] = updated
        if decision_id in self._pending:
            self._pending.remove(decision_id)
        return updated

    def pending(self) -> list[ApprovalDecision]:
        return [self._decisions[did] for did in self._pending]

    def stats(self) -> dict[str, Any]:
        total = len(self._decisions)
        if total == 0:
            return {"total": 0, "approved": 0, "rejected": 0, "pending": 0}
        return {"total": total, "approved": sum(1 for d in self._decisions.values() if d.authorized),
                "rejected": sum(1 for d in self._decisions.values() if not d.authorized), "pending": len(self._pending)}


class PolicyRuntime:
    """Runtime policy enforcement — checks every action against governance rules."""

    def __init__(self) -> None:
        self._violations: list[dict[str, Any]] = []

    def enforce(self, risk_level: str, action: str, allowed_actions: list[str], forbidden_actions: list[str]) -> dict[str, Any]:
        if action in forbidden_actions:
            self._violations.append({"risk": risk_level, "action": action, "result": "BLOCKED", "reason": "forbidden_action", "timestamp": now_iso()})
            return {"allowed": False, "reason": "forbidden_action"}
        if action not in allowed_actions:
            self._violations.append({"risk": risk_level, "action": action, "result": "BLOCKED", "reason": "not_allowed", "timestamp": now_iso()})
            return {"allowed": False, "reason": "not_allowed"}
        approval = RISK_APPROVAL_MAP.get(risk_level, ApprovalLevel.CONFIRM)
        if approval == ApprovalLevel.BLOCKED:
            self._violations.append({"risk": risk_level, "action": action, "result": "BLOCKED", "reason": "R4_blocked", "timestamp": now_iso()})
            return {"allowed": False, "reason": "R4_blocked"}
        return {"allowed": True, "approval_level": approval.value}

    def violations(self) -> list[dict[str, Any]]:
        return list(self._violations)
