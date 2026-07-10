from __future__ import annotations

from datetime import datetime, timedelta, timezone
import threading
from typing import Any

from .db import SQLiteStore
from .events import EventBus
from .models import ApprovalRequest, ApprovalStatus, RiskLevel, WriterLease, new_id, now_iso


class PolicyEngine:
    """Risk policy: low-risk local work can run, consequential actions need a human."""

    APPROVAL_LEVELS = {RiskLevel.R2.value, RiskLevel.R3.value, RiskLevel.R4.value}

    def requires_approval(self, risk_level: RiskLevel) -> bool:
        return risk_level.value in self.APPROVAL_LEVELS

    def allows_tool(self, tool_name: str, risk_level: RiskLevel, safe_mode: bool = False) -> tuple[bool, str]:
        if safe_mode and tool_name not in {"file_read", "browser_readonly"}:
            return False, "safe_mode_allows_read_only_tools"
        if risk_level == RiskLevel.R4:
            return False, "R4_actions_are_never_automatic"
        if tool_name in {"shell", "run_command"}:
            return False, "command_execution_requires_sandboxed_tool"
        return True, "policy_allows"


class ApprovalEngine:
    def __init__(self, store: SQLiteStore, events: EventBus):
        self.store = store
        self.events = events

    def request(
        self,
        mission_id: str,
        action: str,
        risk_level: RiskLevel,
        rationale: str,
        impact: list[str],
        trace_id: str,
        *,
        affected_resources: list[str] | None = None,
        external_effect: bool = False,
        reversible: bool = True,
        rollback_plan: dict[str, Any] | None = None,
        estimated_cost: float = 0.0,
        approval_scope: str = "single_action",
        expires_in_seconds: int = 900,
    ) -> ApprovalRequest:
        approval = ApprovalRequest(
            mission_id=mission_id, action=action, risk_level=risk_level, rationale=rationale,
            reason=rationale, impact=impact, affected_resources=affected_resources or [],
            external_effect=external_effect, reversible=reversible, rollback_plan=rollback_plan or {},
            estimated_cost=estimated_cost, approval_scope=approval_scope,
            expires_at=(datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).isoformat(),
        )
        self.store.save_record(approval.approval_id, "approval", approval.model_dump(mode="json"), approval.created_at, mission_id)
        self.events.publish("approval.requested", mission_id, "mission", "governance", trace_id, {"approval_id": approval.approval_id, "risk_level": risk_level.value, "action": action, "scope": approval_scope})
        return approval

    def decide(self, approval_id: str, approved: bool | None, actor: str, note: str, trace_id: str, decision: str | None = None, scope: str | None = None) -> ApprovalRequest:
        raw = self.store.get_record(approval_id)
        if not raw:
            raise KeyError(f"approval_not_found:{approval_id}")
        approval = ApprovalRequest.model_validate(raw)
        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"approval_already_decided:{approval.status}")
        if approval.expires_at and datetime.fromisoformat(approval.expires_at) <= datetime.now(timezone.utc):
            approval.status = ApprovalStatus.EXPIRED
            self.store.save_record(approval.approval_id, "approval", approval.model_dump(mode="json"), approval.created_at, approval.mission_id)
            raise PermissionError("approval_expired")
        decision = decision or ("approved" if approved else "rejected")
        if decision in {"approve_once", "approve_mission", "approved"}:
            approval.status = ApprovalStatus.APPROVED
            approval.approval_scope = scope or ("single_action" if decision == "approve_once" else approval.approval_scope)
        elif decision in {"request_changes", "changes_requested"}:
            approval.status = ApprovalStatus.CHANGES_REQUESTED
        elif decision == "pause_mission":
            approval.status = ApprovalStatus.PAUSED
        else:
            approval.status = ApprovalStatus.REJECTED
        approval.decided_by = actor
        approval.decision_note = note
        approval.decision_action = decision
        approval.decided_at = now_iso()
        self.store.save_record(approval.approval_id, "approval", approval.model_dump(mode="json"), approval.created_at, approval.mission_id)
        self.events.publish("approval.decided", approval.mission_id, "mission", actor, trace_id, {"approval_id": approval_id, "status": approval.status.value, "decision": decision, "scope": approval.approval_scope})
        return approval

    def get(self, approval_id: str) -> ApprovalRequest | None:
        raw = self.store.get_record(approval_id)
        return ApprovalRequest.model_validate(raw) if raw else None

    def list(self, mission_id: str | None = None) -> list[dict]:
        return self.store.list_records("approval", mission_id)


class WriterLeaseManager:
    def __init__(self, store: SQLiteStore, events: EventBus):
        self.store = store
        self.events = events
        self._lock = threading.RLock()

    def _active(self, lease: WriterLease) -> bool:
        expires = datetime.fromisoformat(lease.expires_at)
        return lease.active and expires > datetime.now(timezone.utc)

    def acquire(self, resource_id: str, writer: str, trace_id: str, ttl_seconds: int = 300) -> WriterLease:
        with self._lock:
            existing = self.store.list_records("lease")
            for raw in existing:
                lease = WriterLease.model_validate(raw)
                if lease.resource_id == resource_id and self._active(lease) and lease.writer != writer:
                    raise RuntimeError(f"writer_lease_conflict:{resource_id}:{lease.writer}")
            expiry = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
            lease = WriterLease(resource_id=resource_id, writer=writer, trace_id=trace_id, expires_at=expiry)
            self.store.save_record(lease.lease_id, "lease", lease.model_dump(mode="json"), now_iso())
            self.events.publish("governance.writer_lease.acquired", resource_id, "resource", writer, trace_id, {"lease_id": lease.lease_id})
            return lease

    def release(self, lease_id: str, writer: str, trace_id: str) -> None:
        raw = self.store.get_record(lease_id)
        if not raw:
            raise KeyError(f"lease_not_found:{lease_id}")
        lease = WriterLease.model_validate(raw)
        if lease.writer != writer:
            raise PermissionError("only_lease_owner_can_release")
        lease.active = False
        self.store.save_record(lease.lease_id, "lease", lease.model_dump(mode="json"), lease.expires_at)
        self.events.publish("governance.writer_lease.released", lease.resource_id, "resource", writer, trace_id, {"lease_id": lease_id})

    def list(self) -> list[dict]:
        return self.store.list_records("lease")
