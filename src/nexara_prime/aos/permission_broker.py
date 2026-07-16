"""Risk-based permission broker — auto-approves R0-R2, escalates R3-R4."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .command_classifier import CommandClassifier, RiskLevel


@dataclass
class PermissionDecision:
    command: str
    risk_level: RiskLevel
    decision: str  # "auto_approved", "policy_approved", "escalated", "denied"
    reason: str
    decision_id: str = ""
    mission_id: str = ""
    worker_id: str = ""
    decided_at: str = ""
    evidence_ref: str = ""


class PermissionBroker:
    """Unified permission broker for all workers.

    R0-R1: auto-approved.
    R2: auto-approved if policy allows and reversible.
    R3: auto-approved only for whitelisted actions.
    R4: always escalated to human.
    """

    def __init__(self, classifier: CommandClassifier | None = None) -> None:
        self._classifier = classifier or CommandClassifier()
        self._decisions: list[PermissionDecision] = []
        self._r3_whitelist: set[str] = {
            "gh pr create", "gh pr edit", "gh pr view",
            "git push origin work/",  # work branches only
        }

    def evaluate(
        self, command: str, *,
        mission_id: str = "", worker_id: str = "",
        working_directory: str = "",
    ) -> PermissionDecision:
        classification = self._classifier.classify(command)
        risk = classification.risk_level
        now = datetime.now(timezone.utc).isoformat()

        decision_id = hashlib.sha256(
            f"{command}:{mission_id}:{worker_id}:{now}".encode()
        ).hexdigest()[:16]

        if risk in (RiskLevel.R0, RiskLevel.R1):
            decision = PermissionDecision(
                command=command, risk_level=risk, decision="auto_approved",
                reason=f"{risk.value} — always auto-approved", decision_id=decision_id,
                mission_id=mission_id, worker_id=worker_id, decided_at=now,
            )
        elif risk == RiskLevel.R2:
            if classification.reversible:
                decision = PermissionDecision(
                    command=command, risk_level=risk, decision="auto_approved",
                    reason="R2 reversible — auto-approved", decision_id=decision_id,
                    mission_id=mission_id, worker_id=worker_id, decided_at=now,
                )
            else:
                decision = PermissionDecision(
                    command=command, risk_level=risk, decision="escalated",
                    reason="R2 non-reversible — requires policy check",
                    decision_id=decision_id, mission_id=mission_id,
                    worker_id=worker_id, decided_at=now,
                )
        elif risk == RiskLevel.R3:
            if self._is_r3_whitelisted(command):
                decision = PermissionDecision(
                    command=command, risk_level=risk, decision="auto_approved",
                    reason="R3 whitelisted action", decision_id=decision_id,
                    mission_id=mission_id, worker_id=worker_id, decided_at=now,
                )
            else:
                decision = PermissionDecision(
                    command=command, risk_level=risk, decision="escalated",
                    reason="R3 requires human approval", decision_id=decision_id,
                    mission_id=mission_id, worker_id=worker_id, decided_at=now,
                )
        else:  # R4
            decision = PermissionDecision(
                command=command, risk_level=risk, decision="escalated",
                reason="R4 always requires human approval", decision_id=decision_id,
                mission_id=mission_id, worker_id=worker_id, decided_at=now,
            )

        self._decisions.append(decision)
        return decision

    def _is_r3_whitelisted(self, command: str) -> bool:
        for pattern in self._r3_whitelist:
            if pattern in command:
                return True
        return False

    @property
    def auto_approved_count(self) -> int:
        return sum(1 for d in self._decisions if d.decision == "auto_approved")

    @property
    def escalated_count(self) -> int:
        return sum(1 for d in self._decisions if d.decision == "escalated")

    def get_decision(self, decision_id: str) -> PermissionDecision | None:
        for d in self._decisions:
            if d.decision_id == decision_id:
                return d
        return None

    def to_evidence(self) -> dict[str, Any]:
        return {
            "total_decisions": len(self._decisions),
            "auto_approved": self.auto_approved_count,
            "escalated": self.escalated_count,
            "decisions": [
                {
                    "id": d.decision_id, "command": d.command[:80],
                    "risk": d.risk_level.value, "decision": d.decision,
                }
                for d in self._decisions[-20:]  # last 20
            ],
        }
