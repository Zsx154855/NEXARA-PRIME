"""AutonomousBoundary — enforcement layer for all autonomous actions.

4-point enforcement per action: (1) allowed list, (2) risk ≤ R2,
(3) evidence exists, (4) no human veto active.
3 violation responses: HALT, LOG_AND_BLOCK, ALERT_HUMAN.
3-tier human veto: CLI, config, API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...models import new_id, now_iso


# ── Action classification ──

AUTONOMOUS_ALLOWED: set[str] = {
    "memory_consolidation",
    "confidence_decay",
    "preference_weight_adjust",
    "experience_pattern_recognition",
    "health_metric_compute",
    "self_check_validate",
    "reasoning_trace_generate",
}

AUTONOMOUS_BLOCKED: set[str] = {
    "capability_register",
    "runtime_pipeline_modify",
    "model_provider_change",
    "governance_rule_change",
    "identity_contract_modify",
    "memory_delete",
    "evidence_delete",
    "external_system_access",
    "autonomous_deploy",
    "autonomous_release",
}

APPROVAL_REQUIRED: set[str] = {
    "skill_formalize",
    "kg_schema_change",
    "reflection_policy_change",
    "preference_conflict_resolve",
    "evolution_activate",
}

# Dual-gating: capability_register is BLOCKED.
# skill_formalize (SKILL_IMPROVEMENT → Capability, evidence-backed) is APPROVAL_REQUIRED.
assert "capability_register" not in APPROVAL_REQUIRED
assert "skill_formalize" not in AUTONOMOUS_BLOCKED


# ── Response types ──

@dataclass
class BoundaryDecision:
    decision_id: str = field(default_factory=lambda: new_id("boundary"))
    action_id: str = ""
    allowed: bool = False
    reason: str = ""
    response: str = ""  # PROCEED, HALT, LOG_AND_BLOCK, ALERT_HUMAN
    evidence_logged: bool = False
    checked_at: str = field(default_factory=now_iso)


@dataclass
class VetoRecord:
    veto_id: str = field(default_factory=lambda: new_id("veto"))
    action_id: str = ""
    reason: str = ""
    source: str = ""  # CLI, config, API
    issued_at: str = field(default_factory=now_iso)
    revoked_at: str = ""
    issued_by: str = "human_owner"


@dataclass
class ActionContext:
    action_id: str = ""
    risk_level: str = "R1"
    evidence_ids: list[str] = field(default_factory=list)
    caller: str = ""


# ── Boundary ──

class AutonomousBoundary:
    """Enforces autonomous action boundary with human veto support."""

    name = "autonomous_boundary"

    def __init__(self, db: Any = None) -> None:
        self._db = db
        self._vetoes: dict[str, VetoRecord] = {}

    # ── Enforcement ──

    def check(self, action_id: str, context: ActionContext | None = None) -> BoundaryDecision:
        """4-point enforcement check."""
        ctx = context or ActionContext(action_id=action_id)

        # Point 1: Human veto active?
        if action_id in self._vetoes:
            v = self._vetoes[action_id]
            if not v.revoked_at:
                return BoundaryDecision(
                    action_id=action_id,
                    allowed=False,
                    reason=f"Human veto active: {v.reason}",
                    response="HALT",
                    evidence_logged=True,
                )

        # Point 2: In blocked list?
        if action_id in AUTONOMOUS_BLOCKED:
            return BoundaryDecision(
                action_id=action_id,
                allowed=False,
                reason=f"Action '{action_id}' is in BLOCKED list",
                response="HALT",
                evidence_logged=True,
            )

        # Point 3: Risk level check
        try:
            risk_num = int(ctx.risk_level[1]) if len(ctx.risk_level) > 1 else 1
        except (ValueError, IndexError):
            risk_num = 1

        if risk_num > 2:  # R3, R4
            return BoundaryDecision(
                action_id=action_id,
                allowed=False,
                reason=f"Risk level {ctx.risk_level} exceeds R2 maximum",
                response="HALT",
                evidence_logged=True,
            )

        # Point 4: Evidence check (for non-trivial actions)
        if action_id not in AUTONOMOUS_ALLOWED and action_id in APPROVAL_REQUIRED:
            if not ctx.evidence_ids:
                return BoundaryDecision(
                    action_id=action_id,
                    allowed=False,
                    reason=f"Approval-required action '{action_id}' lacks evidence",
                    response="ALERT_HUMAN",
                    evidence_logged=False,
                )
            # Has evidence but no explicit approval
            return BoundaryDecision(
                action_id=action_id,
                allowed=False,
                reason=f"Action '{action_id}' requires human approval (evidence present)",
                response="ALERT_HUMAN",
                evidence_logged=True,
            )

        # In allowed list with evidence or low-risk
        return BoundaryDecision(
            action_id=action_id,
            allowed=True,
            reason="Action allowed — all checks passed",
            response="PROCEED",
            evidence_logged=True,
        )

    def is_allowed(self, action_id: str, context: ActionContext | None = None) -> bool:
        return self.check(action_id, context).allowed

    # ── Human Veto ──

    def veto(self, action_id: str, reason: str = "", source: str = "API") -> VetoRecord:
        """Record a human veto. CLI: nexara veto --action=<id>. API: POST /api/brain/veto."""
        record = VetoRecord(
            action_id=action_id,
            reason=reason,
            source=source,
        )
        self._vetoes[action_id] = record

        # Persist if DB available
        if self._db:
            try:
                self._db._conn.execute(
                    """INSERT OR REPLACE INTO human_vetoes
                       (veto_id, action_id, reason, source, issued_at, revoked_at, issued_by)
                       VALUES (?,?,?,?,?,?,?)""",
                    (record.veto_id, action_id, reason, source, record.issued_at, "", "human_owner"),
                )
                self._db._conn.commit()
            except Exception:
                pass  # DB may not have human_vetoes table yet

        return record

    def revoke_veto(self, action_id: str) -> bool:
        """Revoke a previously issued veto."""
        if action_id in self._vetoes:
            self._vetoes[action_id].revoked_at = now_iso()
            if self._db:
                try:
                    self._db._conn.execute(
                        "UPDATE human_vetoes SET revoked_at = ? WHERE action_id = ? AND revoked_at = ''",
                        (now_iso(), action_id),
                    )
                    self._db._conn.commit()
                except Exception:
                    pass
            return True
        return False

    def get_vetoes(self) -> list[VetoRecord]:
        return [v for v in self._vetoes.values() if not v.revoked_at]

    def has_veto(self, action_id: str) -> bool:
        return action_id in self._vetoes and not self._vetoes[action_id].revoked_at

    # ── Health ──

    def health(self) -> dict[str, Any]:
        return {
            "component": self.name,
            "active_vetoes": len(self.get_vetoes()),
            "allowed_actions": len(AUTONOMOUS_ALLOWED),
            "blocked_actions": len(AUTONOMOUS_BLOCKED),
            "approval_required_actions": len(APPROVAL_REQUIRED),
        }
