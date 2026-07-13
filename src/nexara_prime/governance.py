from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import threading
from typing import Any

from .db import SQLiteStore
from .events import EventBus
from .models import (
    ApprovalRequest,
    ApprovalStatus,
    Event,
    RiskLevel,
    WriterLease,
    new_id,
    now_iso,
)


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

    @staticmethod
    def _transition_event_id(idempotency_key: str) -> str:
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:24]
        return f"evt_{digest}"

    def _commit_transition(
        self,
        approval: ApprovalRequest,
        *,
        expected_integrity_sha256: str,
        event_type: str,
        actor: str,
        trace_id: str,
        event_payload: dict[str, Any],
    ) -> None:
        idempotency_key = f"{event_type}:{approval.approval_id}"
        event = Event(
            event_id=self._transition_event_id(idempotency_key),
            event_type=event_type,
            aggregate_id=approval.mission_id,
            aggregate_type="mission",
            actor=actor,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            payload=event_payload,
        )
        result = self.store.repair_record_event(
            approval.approval_id,
            record_type="approval",
            expected_integrity_sha256=expected_integrity_sha256,
            new_payload=approval.model_dump(mode="json"),
            event=event.model_dump(mode="json"),
        )
        if result is None:
            raise RuntimeError("approval_decision_conflict")
        event_inserted, persisted = result
        if event_inserted:
            self.events.notify_persisted(Event.model_validate(persisted))

    def request_origin_is_valid(
        self,
        envelope: dict[str, Any],
        approval: ApprovalRequest,
    ) -> bool:
        original = approval.model_dump(mode="json")
        original.update(
            {
                "status": ApprovalStatus.PENDING.value,
                "decided_by": None,
                "decision_note": None,
                "decision_action": None,
                "decided_at": None,
            }
        )
        return self.store.record_origin_matches(envelope, original)

    def decision_transition_is_valid(self, approval: ApprovalRequest) -> bool:
        if not approval.decided_by or not approval.decided_at:
            return False
        expected_status = approval.status.value
        for event in self.store.list_events(approval.mission_id):
            payload = event.get("payload", {})
            if (
                event.get("event_type") == "approval.decided"
                and event.get("actor") == approval.decided_by
                and payload.get("approval_id") == approval.approval_id
                and payload.get("status") == expected_status
                and payload.get("decision") == approval.decision_action
                and payload.get("scope") == approval.approval_scope
            ):
                return True
        return False

    def consumption_transition_exists(self, approval: ApprovalRequest) -> bool:
        for event in self.store.list_events(approval.mission_id):
            payload = event.get("payload", {})
            if (
                event.get("event_type") == "approval.consumed"
                and event.get("aggregate_type") == "mission"
                and payload.get("approval_id") == approval.approval_id
                and payload.get("action") == approval.action
                and payload.get("risk_level") == approval.risk_level.value
                and payload.get("executor_id") == approval.executor_id
                and payload.get("proposal_sha256") == approval.proposal_sha256
            ):
                return True
        return False

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
        executor_id: str | None = None,
        proposal_sha256: str | None = None,
        expires_in_seconds: int = 900,
    ) -> ApprovalRequest:
        approval = ApprovalRequest(
            mission_id=mission_id, action=action, risk_level=risk_level, rationale=rationale,
            reason=rationale, impact=impact, affected_resources=affected_resources or [],
            external_effect=external_effect, reversible=reversible, rollback_plan=rollback_plan or {},
            estimated_cost=estimated_cost, approval_scope=approval_scope, executor_id=executor_id,
            proposal_sha256=proposal_sha256,
            expires_at=(datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).isoformat(),
        )
        request_payload = approval.model_dump(mode="json")
        event = Event(
            event_type="approval.requested",
            aggregate_id=mission_id,
            aggregate_type="mission",
            actor="governance",
            trace_id=trace_id,
            payload={
                "approval_id": approval.approval_id,
                "risk_level": risk_level.value,
                "action": action,
                "scope": approval_scope,
                "request": request_payload,
            },
        )
        record_inserted, event_inserted, persisted = (
            self.store.save_record_and_event_if_absent(
                approval.approval_id,
                "approval",
                request_payload,
                approval.created_at,
                event.model_dump(mode="json"),
                mission_id,
            )
        )
        if not record_inserted or persisted is None:
            raise RuntimeError("approval_request_conflict")
        if event_inserted:
            self.events.notify_persisted(Event.model_validate(persisted))
        return approval

    def decide(self, approval_id: str, approved: bool | None, actor: str, note: str, trace_id: str, decision: str | None = None, scope: str | None = None) -> ApprovalRequest:
        envelope = self.store.get_record_envelope(approval_id)
        if not envelope:
            raise KeyError(f"approval_not_found:{approval_id}")
        if envelope.get("record_type") != "approval":
            raise ValueError("approval_record_type_invalid")
        approval = ApprovalRequest.model_validate(envelope["payload"])
        if (
            envelope.get("record_id") != approval_id
            or approval.approval_id != approval_id
            or envelope.get("mission_id") != approval.mission_id
            or not self.request_origin_is_valid(envelope, approval)
        ):
            raise ValueError("approval_integrity_invalid")
        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"approval_already_decided:{approval.status}")
        if not actor.strip():
            raise ValueError("approval_decision_actor_required")
        expiry = datetime.fromisoformat(approval.expires_at) if approval.expires_at else None
        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry and expiry <= datetime.now(timezone.utc):
            approval.status = ApprovalStatus.EXPIRED
            self._commit_transition(
                approval,
                expected_integrity_sha256=envelope["integrity_sha256"],
                event_type="approval.expired",
                actor="governance",
                trace_id=trace_id,
                event_payload={
                    "approval_id": approval.approval_id,
                    "status": ApprovalStatus.EXPIRED.value,
                    "expires_at": approval.expires_at,
                },
            )
            raise PermissionError("approval_expired")
        decision = decision or ("approved" if approved else "rejected")
        if decision in {"approve_once", "approve_mission", "approved"}:
            approval.status = ApprovalStatus.APPROVED
            if scope is not None and scope != approval.approval_scope:
                raise ValueError("approval_decision_scope_mismatch")
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
        self._commit_transition(
            approval,
            expected_integrity_sha256=envelope["integrity_sha256"],
            event_type="approval.decided",
            actor=actor,
            trace_id=trace_id,
            event_payload={
                "approval_id": approval_id,
                "status": approval.status.value,
                "decision": decision,
                "scope": approval.approval_scope,
                "action": approval.action,
                "risk_level": approval.risk_level.value,
                "executor_id": approval.executor_id,
                "proposal_sha256": approval.proposal_sha256,
                "decided_at": approval.decided_at,
            },
        )
        return approval

    def get(self, approval_id: str) -> ApprovalRequest | None:
        envelope = self.store.get_record_envelope(approval_id)
        if not envelope:
            return None
        if envelope.get("record_type") != "approval":
            raise ValueError("approval_record_type_invalid")
        approval = ApprovalRequest.model_validate(envelope["payload"])
        if (
            envelope.get("record_id") != approval_id
            or approval.approval_id != approval_id
            or envelope.get("mission_id") != approval.mission_id
            or not self.request_origin_is_valid(envelope, approval)
        ):
            raise ValueError("approval_integrity_invalid")
        return approval

    def list(self, mission_id: str | None = None) -> list[dict]:
        approvals: list[dict] = []
        for envelope in self.store.list_record_envelopes("approval", mission_id):
            approval = ApprovalRequest.model_validate(envelope["payload"])
            if (
                envelope.get("record_id") != approval.approval_id
                or envelope.get("mission_id") != approval.mission_id
                or not self.request_origin_is_valid(envelope, approval)
            ):
                raise ValueError("approval_integrity_invalid")
            approvals.append(approval.model_dump(mode="json"))
        return approvals


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
