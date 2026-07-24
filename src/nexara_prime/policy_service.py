"""PolicyService — runnable wrapper for PolicyEngine + ApprovalEngine + WriterLeaseManager.

G3-B: Extracts existing policy components into a lifecycle-managed service.
Does NOT modify governance.py. WRAPS, not replaces.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .db import SQLiteStore
from .events import EventBus
from .governance import ApprovalEngine, PolicyEngine, WriterLeaseManager
from .models import RiskLevel, now_iso


@dataclass
class PolicyServiceHealth:
    """Health status for the PolicyService."""
    status: str = "unknown"  # healthy, degraded, stopped
    policy_engine: bool = False
    approval_engine: bool = False
    lease_manager: bool = False
    active_leases: int = 0
    pending_approvals: int = 0
    started_at: str = ""
    checked_at: str = ""


class PolicyService:
    """Runnable service wrapping PolicyEngine + ApprovalEngine + WriterLeaseManager.

    Usage:
        store = SQLiteStore(...)
        events = EventBus(store)
        policy = PolicyService(store, events)
        policy.start()
        ...
        policy.stop()
    """

    def __init__(self, store: SQLiteStore, events: EventBus) -> None:
        self._policy = PolicyEngine()
        self._approvals = ApprovalEngine(store, events)
        self._leases = WriterLeaseManager(store, events)
        self._started = False
        self._started_at = ""

    # ── Service Lifecycle ──

    def start(self) -> None:
        self._started = True
        self._started_at = now_iso()

    def stop(self) -> None:
        self._started = False

    @property
    def running(self) -> bool:
        return self._started

    # ── Health ──

    def health(self) -> PolicyServiceHealth:
        return PolicyServiceHealth(
            status="healthy" if self._started else "stopped",
            policy_engine=self._policy is not None,
            approval_engine=self._approvals is not None,
            lease_manager=self._leases is not None,
            active_leases=len(self._leases.list()) if self._started else 0,
            pending_approvals=len(self._approvals.list()) if self._started else 0,
            started_at=self._started_at,
            checked_at=now_iso(),
        )

    # ── Policy Accessors (delegating to PolicyEngine) ──

    @property
    def policy(self) -> PolicyEngine:
        return self._policy

    def requires_approval(self, risk_level: RiskLevel) -> bool:
        return self._policy.requires_approval(risk_level)

    def allows_tool(self, tool_name: str, risk_level: RiskLevel, safe_mode: bool = False) -> tuple[bool, str]:
        return self._policy.allows_tool(tool_name, risk_level, safe_mode)

    # ── Approval Accessors (delegating to ApprovalEngine) ──

    @property
    def approvals(self) -> ApprovalEngine:
        return self._approvals

    def request_approval(
        self, mission_id: str, action: str, rationale: str,
        risk_level: RiskLevel = RiskLevel.R2, external_effect: bool = False,
    ) -> Any:
        return self._approvals.request(mission_id, action, rationale, risk_level, external_effect)

    def decide_approval(self, approval_id: str, approved: bool | None, actor: str, note: str = "") -> Any:
        return self._approvals.decide(approval_id, approved, actor, note)

    def list_approvals(self, mission_id: str | None = None) -> list[dict[str, Any]]:
        return self._approvals.list(mission_id)

    # ── Lease Accessors (delegating to WriterLeaseManager) ──

    @property
    def leases(self) -> WriterLeaseManager:
        return self._leases

    def acquire_lease(self, resource_id: str, writer: str, trace_id: str, ttl_seconds: int = 300) -> Any:
        return self._leases.acquire(resource_id, writer, trace_id, ttl_seconds)

    def release_lease(self, lease_id: str, writer: str, trace_id: str) -> None:
        self._leases.release(lease_id, writer, trace_id)

    def list_leases(self) -> list[dict[str, Any]]:
        return self._leases.list()
